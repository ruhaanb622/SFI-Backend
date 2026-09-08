from flask_restful import Resource
from datetime import datetime
import requests
from __init__ import app

class GitHubUser(Resource):
    def get(self, uid):
        url = app.config['GITHUB_API_URL'] + f'/users/{uid}'
        token = app.config['GITHUB_TOKEN']
        if not token:
            # assume Test Server and not using GitHub API  
            return {'message': 'GITHUB_TOKEN not set'}, 200

        try:
            headers = {'Authorization': f'token {token}'}
            response = requests.get(url, headers=headers)

            if response.status_code == 404:
                return {'message': f'Invalid UID {uid}'}, 404
            elif response.status_code != 200:
                return {'message': 'GitHub API failed to fetch user data'}, response.status_code

            return response.json(), 200

        except Exception as e:
            return {'message': str(e)}, 500
    
    def get_profile_links(self, uid):
        user_data, status_code = self.get(uid)
        if status_code != 200:
            return user_data, status_code
        
        profile_links = {
            'profile_url': user_data.get('html_url'),
            'repos_url': user_data.get('repos_url')
        }
        return profile_links, 200

    def make_github_graphql_request(self, query, variables):
        url = "https://api.github.com/graphql"
        token = app.config['GITHUB_TOKEN']
        
        if not token:
            return {'message': 'GITHUB_TOKEN not set'}, 400

        headers = {'Authorization': f'bearer {token}'}
        try:
            response = requests.post(url, json={'query': query, 'variables': variables}, headers=headers)
            
            if response.status_code != 200:
                return {'message': 'GitHub API failed to fetch data'}, response.status_code

            return response.json(), 200
        except Exception as e:
            return {'message': str(e)}, 500

    def get_commit_stats(self, uid, start_date_str, end_date_str):
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        start_date_iso = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_date_iso = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')

        repo_query = """
        query($login: String!, $since: GitTimestamp!, $until: GitTimestamp!) {
        user(login: $login) {
            repositoriesContributedTo(first: 50, contributionTypes: [COMMIT], includeUserRepositories: true) {
            nodes {
                name
                owner { login }
                defaultBranchRef {
                name
                target {
                    ... on Commit {
                    history(first: 100, since: $since, until: $until) {
                        nodes {
                        committedDate
                        messageHeadline
                        additions
                        deletions
                        url
                        author {
                            user {
                            login
                            }
                        }
                        }
                    }
                    }
                }
                }
            }
            }
        }
        }
        """

        variables = {
            "login": uid,
            "since": start_date_iso,
            "until": end_date_iso
        }

        response_data, status_code = self.make_github_graphql_request(repo_query, variables)
        
        if status_code != 200 or not response_data:
            return {
                'error': 'Failed to fetch data from GitHub'
            }, status_code

        details_of_commits = []
        total_additions = 0
        total_deletions = 0
        total_commits = 0

        try:
            repos = response_data['data']['user']['repositoriesContributedTo']['nodes']
            for repo in repos:
                repo_name = f"{repo['owner']['login']}/{repo['name']}"
                branch = repo.get('defaultBranchRef')
                if not branch or not branch.get('target'):
                    continue

                history = branch['target'].get('history', {}).get('nodes', [])
                for commit in history:
                    author_info = commit.get('author', {}).get('user')
                    if not author_info or author_info.get('login') != uid:
                        continue  # Skip commits not by the specified user

                    additions = commit.get('additions', 0)
                    deletions = commit.get('deletions', 0)
                    total_additions += additions
                    total_deletions += deletions
                    total_commits += 1

                    details_of_commits.append({
                        "repository": repo_name,
                        "date": commit.get('committedDate'),
                        "message": commit.get('messageHeadline'),
                        "additions": additions,
                        "deletions": deletions,
                        "url": commit.get('url')
                    })

        except Exception as e:
            return {
                'error': f'Error processing response: {str(e)}'
            }, 500

        return {
            'total_commit_contributions': total_commits,
            'total_lines_added': total_additions,
            'total_lines_deleted': total_deletions,
            'details_of_commits': details_of_commits
        }, 200

    def get_pr_stats(self, uid, start_date_str, end_date_str):
        query = """
        query($query: String!) {
            search(query: $query, type: ISSUE, first: 100) {
                edges {
                    node {
                        ... on PullRequest {
                            title
                            url
                            createdAt
                            repository {
                                nameWithOwner
                            }
                            author {
                                login
                            }
                            comments(first: 10) {
                                nodes {
                                    body
                                    author {
                                        login
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        search_query = f"type:pr author:{uid} created:{start_date_str}..{end_date_str}"
        variables = {
            "query": search_query
        }
        data, status_code = self.make_github_graphql_request(query, variables)
        if status_code != 200:
            return data, status_code

        pr_stats = data['data']['search']['edges']

        return {'pull_requests': pr_stats}, 200

    def get_issue_stats(self, uid, start_date_str, end_date_str):
        query = """
        query($query: String!) {
            search(query: $query, type: ISSUE, first: 100) {
                edges {
                    node {
                        ... on Issue {
                            title
                            url
                            createdAt
                            repository {
                                nameWithOwner
                            }
                            author {
                                login
                            }
                            comments {
                                totalCount
                                nodes {
                                    body
                                    author {
                                        login
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        search_query = f"type:issue author:{uid} created:{start_date_str}..{end_date_str}"
        variables = {
            "query": search_query
        }
        data, status_code = self.make_github_graphql_request(query, variables)
        if status_code != 200:
            return data, status_code

        issue_stats = data['data']['search']['edges']
        return {'issues': issue_stats}, 200

    def get_total_received_issue_comments(self, user_id, start_date, end_date):
        issues_data, status_code = self.get_issue_stats(user_id, start_date, end_date)
        if status_code != 200:
            return issues_data, status_code
        
        total_comments = 0
        for issue in issues_data["issues"]:
            node = issue.get('node')
            if node and 'comments' in node and node['comments']:
                total_comments += node['comments']['totalCount']
        
        return {"total_received_comments": total_comments}, 200
    
    
    


class GitHubOrg(Resource):
    def get_users(self, org_name):
        url = app.config['GITHUB_API_URL'] + f'/orgs/{org_name}/members'
        token = app.config['GITHUB_TOKEN']
        if not token:
            return {'message': 'GITHUB_TOKEN not set'}, 400

        try:
            headers = {'Authorization': f'token {token}'}
            response = requests.get(url, headers=headers)

            if response.status_code != 200:
                return {'message': 'GitHub API failed to fetch organization members'}, response.status_code

            return response.json(), 200

        except Exception as e:
            return {'message': str(e)}, 500

    def get_repos(self, org_name):
        url = app.config['GITHUB_API_URL'] + f'/orgs/{org_name}/repos'
        token = app.config['GITHUB_TOKEN']
        if not token:
            return {'message': 'GITHUB_TOKEN not set'}, 400

        try:
            headers = {'Authorization': f'token {token}'}
            response = requests.get(url, headers=headers)

            if response.status_code != 200:
                return {'message': 'GitHub API failed to fetch organization repositories'}, response.status_code

            return response.json(), 200

        except Exception as e:
            return {'message': str(e)}, 500
