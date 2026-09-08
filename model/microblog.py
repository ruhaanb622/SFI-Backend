"""
Micro Blog Model
Defines the database schema for micro blog posts with JSON flexibility
"""
from sqlite3 import IntegrityError
from sqlalchemy import Text, JSON
from sqlalchemy.orm.attributes import flag_modified
from __init__ import db
from datetime import datetime
import json




class MicroBlog(db.Model):
   """
   MicroBlog Model
  
   Represents a micro blog post with flexible JSON content and topic organization.
   Supports replies, reactions, and custom frontend attributes through JSON storage.
   """
   __tablename__ = 'microblogs'


   # Primary Key
   id = db.Column(db.Integer, primary_key=True)
  
   # Foreign Keys
   _user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
   _topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=True)  # You'll need a topics table
  
   # Content (280 character limit like Twitter)
   _content = db.Column(db.String(280), nullable=False)
  
   # JSON field for flexible data storage
   _data = db.Column(JSON, nullable=True)
  
   # Metadata
   _timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
   _updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
  
   # Relationships
   user = db.relationship('User', foreign_keys=[_user_id], backref=db.backref('microblogs', lazy=True))
   topic = db.relationship('Topic', foreign_keys=[_topic_id], backref=db.backref('microblogs', lazy=True))


   def __init__(self, user_id, content, topic_id=None, data=None):
       """
       Initialize a new MicroBlog post
      
       Args:
           user_id: ID of the user creating the post
           content: Text content (max 280 characters)
           topic_id: Optional topic/category ID
           data: Optional JSON data for frontend flexibility
       """
       if len(content) > 280:
           raise ValueError("Content must be 280 characters or less")
          
       self._user_id = user_id
       self._content = content
       self._topic_id = topic_id
       self._data = data or {}
       self._timestamp = datetime.utcnow()


   def create(self):
       """Create a new micro blog post in the database"""
       try:
           db.session.add(self)
           db.session.commit()
           return self
       except IntegrityError:
           db.session.rollback()
           return None
       except Exception as e:
           db.session.rollback()
           raise e


   def read(self):
       """Read micro blog data as a dictionary, including topic key and path if available"""
       # Get topic info if available
       topic_key = None
       topic_path = None
       if self.topic:
           topic_key = getattr(self.topic, '_page_key', None)
           topic_path = getattr(self.topic, '_page_path', None)
       base_data = {
           'id': self.id,
           'userId': self._user_id,
           'userName': self.user.name if self.user else 'Unknown',
           'userUid': self.user.uid if self.user else None,
           'content': self._content,
           'topicId': self._topic_id,
           'topicKey': topic_key,
           'topicPath': topic_path,
           'timestamp': self._timestamp.isoformat() if self._timestamp else None,
           'updatedAt': self._updated_at.isoformat() if self._updated_at else None,
           'characterCount': len(self._content),
       }
       # Merge with JSON data, giving priority to base_data for core fields
       if self._data:
           merged_data = {**self._data, **base_data}
       else:
           merged_data = base_data
       return merged_data


   def update(self, content=None, data=None):
       """Update micro blog content and/or data"""
       try:
           if content is not None:
               if len(content) > 280:
                   raise ValueError("Content must be 280 characters or less")
               self._content = content
              
           if data is not None:
               # Merge new data with existing data
               if self._data:
                   self._data.update(data)
               else:
                   self._data = data
                  
           self._updated_at = datetime.utcnow()
           db.session.commit()
           return self
       except Exception as e:
           db.session.rollback()
           raise e


   def get_replies(self):
       """Return replies array; empty list if none or malformed."""
       if not self._data or 'replies' not in self._data or not isinstance(self._data['replies'], list):
           return []
       return self._data['replies']


   def add_reply(self, user_id, reply_content):
       """Add a reply to the JSON data structure, including userName for display."""
       if len(reply_content) > 280:
           raise ValueError("Reply content must be 280 characters or less")
      
       if not self._data:
           self._data = {}
      
       if 'replies' not in self._data or not isinstance(self._data['replies'], list):
           self._data['replies'] = []
      
       # Attempt to include userName for frontend display
       user_name = None
       try:
           from model.user import User
           u = User.query.get(user_id)
           user_name = u.name if u else None
       except Exception:
           user_name = None
      
       reply = {
           'id': len(self._data['replies']) + 1,  # Simple incrementing ID
           'userId': user_id,
           'userName': user_name,
           'content': reply_content,
           'timestamp': datetime.utcnow().isoformat()
       }
      
       self._data['replies'].append(reply)
       self._updated_at = datetime.utcnow()
      
       flag_modified(self, '_data')
      
       try:
           db.session.commit()
           return reply
       except Exception as e:
           db.session.rollback()
           raise e


   def add_reaction(self, user_id, reaction_type):
       """Add a reaction (like, heart, etc.) to the JSON data"""
       if not self._data:
           self._data = {}
          
       if 'reactions' not in self._data:
           self._data['reactions'] = {}
          
       if reaction_type not in self._data['reactions']:
           self._data['reactions'][reaction_type] = []
          
       # Remove user's previous reaction of this type if exists
       self._data['reactions'][reaction_type] = [
           uid for uid in self._data['reactions'][reaction_type] if uid != user_id
       ]
      
       # Add new reaction
       self._data['reactions'][reaction_type].append(user_id)
       self._updated_at = datetime.utcnow()
      
       # CRITICAL: Mark the _data column as modified for SQLAlchemy
       flag_modified(self, '_data')
      
       try:
           db.session.commit()
           db.session.refresh(self)
           return True
       except Exception as e:
           db.session.rollback()
           raise e


   def remove_reaction(self, user_id, reaction_type):
       """Remove a reaction from the JSON data"""
       if not self._data or 'reactions' not in self._data:
           return False
          
       if reaction_type in self._data['reactions']:
           self._data['reactions'][reaction_type] = [
               uid for uid in self._data['reactions'][reaction_type] if uid != user_id
           ]
           self._updated_at = datetime.utcnow()
          
           flag_modified(self, '_data')
          
           try:
               db.session.commit()
               db.session.refresh(self)
               return True
           except Exception as e:
               db.session.rollback()
               raise e
      
       return False
  
   def get_reactions(self):
       """Return reactions dictionary; empty dict if none or malformed."""
       if not self._data or 'reactions' not in self._data or not isinstance(self._data['reactions'], dict):
           return {}
       return self._data['reactions']


   def get_reaction_counts(self):
       """Return a dictionary with reaction counts"""
       reactions = self.get_reactions()
       reaction_counts = {}
       for reaction_type, user_ids in reactions.items():
           reaction_counts[reaction_type] = len(user_ids)
       return reaction_counts


   def user_has_reacted(self, user_id, reaction_type):
       """Check if a user has already reacted with a specific reaction type"""
       reactions = self.get_reactions()
       if reaction_type not in reactions:
           return False
       return user_id in reactions[reaction_type]


   def toggle_reaction(self, user_id, reaction_type):
       """Toggle a reaction - add if not present, remove if present"""
       if self.user_has_reacted(user_id, reaction_type):
           return self.remove_reaction(user_id, reaction_type)
       else:
           return self.add_reaction(user_id, reaction_type)


   def delete(self):
       """Delete the micro blog post"""
       try:
           db.session.delete(self)
           db.session.commit()
           return True
       except Exception as e:
           db.session.rollback()
           raise e


   @staticmethod
   def get_by_id(microblog_id):
       """Get a micro blog post by its ID"""
       return MicroBlog.query.get(microblog_id)


   @staticmethod
   def get_all(limit=50):
       """Get all micro blog posts (most recent first)"""
       microblogs = MicroBlog.query.order_by(MicroBlog._timestamp.desc()).limit(limit).all()
       return [microblog.read() for microblog in microblogs]


   @staticmethod
   def get_by_topic(topic_id, limit=50):
       """Get all micro blog posts for a specific topic"""
       microblogs = MicroBlog.query.filter_by(_topic_id=topic_id).order_by(MicroBlog._timestamp.desc()).limit(limit).all()
       return [microblog.read() for microblog in microblogs]


   @staticmethod
   def get_by_user(user_id, limit=50):
       """Get all micro blog posts by a specific user"""
       microblogs = MicroBlog.query.filter_by(_user_id=user_id).order_by(MicroBlog._timestamp.desc()).limit(limit).all()
       return [microblog.read() for microblog in microblogs]


   @staticmethod
   def search_content(search_term, limit=50):
       """Search micro blog posts by content"""
       microblogs = MicroBlog.query.filter(MicroBlog._content.contains(search_term)).order_by(MicroBlog._timestamp.desc()).limit(limit).all()
       return [microblog.read() for microblog in microblogs]




class Topic(db.Model):
   """
   Topic Model for organizing micro blog posts by page/location
   Represents specific pages or locations in the site where microblogs are embedded
   """
   __tablename__ = 'topics'
  
   id = db.Column(db.Integer, primary_key=True)
  
   # Page identification
   _page_key = db.Column(db.String(100), unique=True, nullable=False)  # Generated from page path
   _page_path = db.Column(db.String(500), nullable=False)  # Full page path/URL
   _page_title = db.Column(db.String(200), nullable=False)  # Human readable title
   _page_description = db.Column(Text, nullable=True)  # Page description/context
  
   # Display settings
   _display_name = db.Column(db.String(100), nullable=True)  # Custom display name
   _color = db.Column(db.String(7), default='#007bff')  # Theme color
   _icon = db.Column(db.String(50), nullable=True)  # Optional icon class/emoji
  
   # Microblog settings
   _allow_anonymous = db.Column(db.Boolean, default=False)  # Allow non-logged users to view
   _moderated = db.Column(db.Boolean, default=False)  # Require approval for posts
   _max_posts_per_user = db.Column(db.Integer, default=10)  # Limit posts per user per topic
  
   # Metadata
   _created_at = db.Column(db.DateTime, default=datetime.utcnow)
   _updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
   _is_active = db.Column(db.Boolean, default=True)  # Enable/disable topic
  
   # Additional JSON settings for flexibility
   _settings = db.Column(JSON, nullable=True)  # Custom settings per topic
  
   # Relationship
   # microblogs backref is provided by MicroBlog.topic relationship
  
   def __init__(self, page_path, page_title, page_description=None, display_name=None,
                color='#007bff', icon=None, allow_anonymous=False, moderated=False,
                max_posts_per_user=10, settings=None):
       """
       Initialize a new Topic for a page location
      
       Args:
           page_path: The path/URL of the page (e.g., '/lessons/flask-intro', '/hacks/javascript')
           page_title: Human readable title (e.g., 'Flask Introduction', 'JavaScript Hacks')
           page_description: Optional description of the page/lesson
           display_name: Custom name for microblog section (defaults to page_title)
           color: Theme color for this topic's microblogs
           icon: Optional icon (emoji or CSS class)
           allow_anonymous: Whether non-logged users can view posts
           moderated: Whether posts need approval
           max_posts_per_user: Limit posts per user (prevent spam)
           settings: Additional JSON settings
       """
       self._page_path = page_path
       self._page_key = self._generate_page_key(page_path)
       self._page_title = page_title
       self._page_description = page_description
       self._display_name = display_name or page_title
       self._color = color
       self._icon = icon
       self._allow_anonymous = allow_anonymous
       self._moderated = moderated
       self._max_posts_per_user = max_posts_per_user
       self._settings = settings or {}
  
   def _generate_page_key(self, page_path):
       """Generate a unique key from page path"""
       import re
       # Remove leading/trailing slashes, replace special chars with underscores
       key = re.sub(r'[^a-zA-Z0-9\-_]', '_', page_path.strip('/'))
       # Remove multiple underscores
       key = re.sub(r'_+', '_', key)
       # Ensure it's not too long
       return key[:100].strip('_')
  
   def create(self):
       """Create a new topic"""
       try:
           db.session.add(self)
           db.session.commit()
           return self
       except IntegrityError as e:
           db.session.rollback()
           return None
       except Exception as e:
           db.session.rollback()
           raise e
  
   def update(self, **kwargs):
       """Update topic settings"""
       try:
           for key, value in kwargs.items():
               if hasattr(self, f'_{key}'):
                   setattr(self, f'_{key}', value)
               elif key == 'settings' and self._settings:
                   self._settings.update(value)
               else:
                   self._settings = self._settings or {}
                   self._settings[key] = value
          
           self._updated_at = datetime.utcnow()
           db.session.commit()
           return self
       except Exception as e:
           db.session.rollback()
           raise e
  
   def read(self):
       """Read topic data as dictionary"""
       return {
           'id': self.id,
           'pageKey': self._page_key,
           'pagePath': self._page_path,
           'pageTitle': self._page_title,
           'pageDescription': self._page_description,
           'displayName': self._display_name,
           'color': self._color,
           'icon': self._icon,
           'allowAnonymous': self._allow_anonymous,
           'moderated': self._moderated,
           'maxPostsPerUser': self._max_posts_per_user,
           'isActive': self._is_active,
           'settings': self._settings,
           'postCount': len(self.microblogs),
           'createdAt': self._created_at.isoformat() if self._created_at else None,
           'updatedAt': self._updated_at.isoformat() if self._updated_at else None
       }
  
   def get_user_post_count(self, user_id):
       """Get number of posts by a specific user in this topic"""
       return MicroBlog.query.filter_by(_topic_id=self.id, _user_id=user_id).count()
  
   def can_user_post(self, user_id):
       """Check if user can post more messages in this topic"""
       if not self._is_active:
           return False
      
       current_count = self.get_user_post_count(user_id)
       return current_count < self._max_posts_per_user
  
   def get_recent_posts(self, limit=10, user_id=None):
       """Get recent posts for this topic"""
       query = MicroBlog.query.filter_by(_topic_id=self.id)
      
       # If not allowing anonymous and no user_id, return empty
       if not self._allow_anonymous and not user_id:
           return []
      
       posts = query.order_by(MicroBlog._timestamp.desc()).limit(limit).all()
       return [post.read() for post in posts]
  
   @staticmethod
   def get_by_page_path(page_path):
       """Get topic by page path"""
       return Topic.query.filter_by(_page_path=page_path).first()
  
   @staticmethod
   def get_by_page_key(page_key):
       """Get topic by page key"""
       return Topic.query.filter_by(_page_key=page_key).first()
  
   @staticmethod
   def get_or_create_for_page(page_path, page_title, **kwargs):
       """Get existing topic or create new one for a page"""
       try:
           # Check if topic already exists
           topic = Topic.get_by_page_path(page_path)
           if topic:
               return topic
          
           # Create new topic
           new_topic = Topic(page_path=page_path, page_title=page_title, **kwargs)
           created_topic = new_topic.create()
          
           if created_topic is None:
               print(f"Failed to create topic for page_path: {page_path}")
               return None
              
           return created_topic
          
       except Exception as e:
           print(f"Error in get_or_create_for_page: {str(e)}")
           return None
  
   @staticmethod
   def get_all_active():
       """Get all active topics"""
       topics = Topic.query.filter_by(_is_active=True).order_by(Topic._page_title).all()
       return [topic.read() for topic in topics]
  
   @staticmethod
   def get_all():
       """Get all topics (including inactive)"""
       topics = Topic.query.order_by(Topic._page_title).all()
       return [topic.read() for topic in topics]
  
   @staticmethod
   def search_by_title(search_term):
       """Search topics by title or description"""
       topics = Topic.query.filter(
           db.or_(
               Topic._page_title.contains(search_term),
               Topic._page_description.contains(search_term)
           )
       ).filter_by(_is_active=True).all()
       return [topic.read() for topic in topics]




def initMicroblogs():
   """Initialize the microblogs and topics tables with sample data"""
   # Import here to avoid circular import
   from __init__ import app
  
   with app.app_context():
       # Check if data already exists
       if Topic.query.first() or MicroBlog.query.first():
           print("MicroBlog tables already contain data. Skipping initialization.")
           return
      
       # Import User model
       from model.user import User
      
       # Get all existing users (should be created by initUsers)
       admin_user = User.query.filter_by(_uid=app.config.get('ADMIN_UID', 'toby')).first()
       default_user = User.query.filter_by(_uid=app.config.get('DEFAULT_UID', 'hop')).first()
       teacher_user = User.query.filter_by(_uid='niko').first()
      
       users = [admin_user, default_user, teacher_user]
       active_users = [u for u in users if u is not None]
      
       if len(active_users) < 2:
           print("Not enough users found. Please run initUsers() first.")
           return
      
       print(f"Found {len(active_users)} users for microblog initialization")
      
       # Create sample topics based on actual page locations
       page_topics = [
           {
               "page_path": "/lessons/flask-introduction",
               "page_title": "Flask Introduction Lesson",
               "page_description": "Learn the basics of Flask web framework",
               "display_name": "Flask Intro Discussion",
               "color": "#28a745",
               "icon": "🐍",
               "allow_anonymous": True,
               "moderated": False,
               "max_posts_per_user": 5
           },
           {
               "page_path": "/hacks/javascript-basics",
               "page_title": "JavaScript Basics Hack",
               "page_description": "Hands-on JavaScript programming exercises",
               "display_name": "JS Hack Comments",
               "color": "#ffc107",
               "icon": "⚡",
               "allow_anonymous": False,
               "moderated": True,
               "max_posts_per_user": 3
           },
           {
               "page_path": "/projects/portfolio-showcase",
               "page_title": "Portfolio Showcase",
               "page_description": "Student portfolio presentations and feedback",
               "display_name": "Portfolio Feedback",
               "color": "#dc3545",
               "icon": "🎨",
               "allow_anonymous": False,
               "moderated": False,
               "max_posts_per_user": 10
           },
           {
               "page_path": "/general/daily-standup",
               "page_title": "Daily Standup",
               "page_description": "Daily progress updates and announcements",
               "display_name": "Daily Updates",
               "color": "#007bff",
               "icon": "📅",
               "allow_anonymous": False,
               "moderated": False,
               "max_posts_per_user": 1,
               "settings": {
                   "daily_reset": True,
                   "auto_archive": 7  # Archive after 7 days
               }
           },
           {
               "page_path": "/resources/study-materials",
               "page_title": "Study Materials",
               "page_description": "Shared study resources and tips",
               "display_name": "Study Discussion",
               "color": "#6f42c1",
               "icon": "📚",
               "allow_anonymous": True,
               "moderated": False,
               "max_posts_per_user": 15
           }
       ]
      
       created_topics = []
       for topic_data in page_topics:
           topic = Topic(**topic_data)
           db.session.add(topic)
           created_topics.append(topic)
      
       db.session.flush()  # Get topic IDs
      
       # Create sample micro blog posts for different pages
       sample_posts = [
           {
               "content": "Just finished the Flask intro lesson! The routing concept is clearer now",
               "topic_id": created_topics[0].id,  # Flask Introduction
               "data": {
                   "lessonProgress": "completed",
                   "rating": 5,
                   "hashtags": ["flask", "python", "webdev"],
                   "reactions": {"👍": [], "🎉": []},
                   "replies": []
               }
           },
           {
               "content": "The JavaScript array methods are tricky! Anyone have tips for remembering map vs filter?",
               "topic_id": created_topics[1].id,  # JavaScript Basics
               "data": {
                   "helpRequested": True,
                   "difficulty": "medium",
                   "hashtags": ["javascript", "arrays", "help"],
                   "reactions": {"🤔": [], "💡": []},
                   "replies": []
               }
           },
           {
               "content": "Excited to share my portfolio! Added a new React project with dark mode toggle",
               "topic_id": created_topics[2].id,  # Portfolio Showcase
               "data": {
                   "projectType": "react",
                   "features": ["dark-mode", "responsive"],
                   "seeking": "feedback",
                   "hashtags": ["portfolio", "react", "showcase"],
                   "reactions": {"❤️": [], "🔥": []},
                   "replies": []
               }
           },
           {
               "content": "Today: Working on database models, planning API endpoints, studying for quiz tomorrow",
               "topic_id": created_topics[3].id,  # Daily Standup
               "data": {
                   "standupType": "daily",
                   "tasks": ["database-models", "api-planning", "quiz-prep"],
                   "blockers": [],
                   "mood": "productive",
                   "hashtags": ["standup", "progress"],
                   "reactions": {"💪": []},
                   "replies": []
               }
           },
           {
               "content": "Great study resource: MDN docs have interactive examples. Really helpful for learning!",
               "topic_id": created_topics[4].id,  # Study Materials
               "data": {
                   "resourceType": "documentation",
                   "resourceUrl": "https://developer.mozilla.org",
                   "subject": "javascript",
                   "recommendation": True,
                   "hashtags": ["resources", "javascript", "documentation"],
                   "reactions": {"📚": [], "👍": []},
                   "replies": []
               }
           }
       ]
      
       # Update sample_posts to include user assignment
       for i, post_data in enumerate(sample_posts):
           # Assign users cyclically to posts
           assigned_user = active_users[i % len(active_users)]
           microblog = MicroBlog(
               user_id=assigned_user.id,
               content=post_data["content"],
               topic_id=post_data["topic_id"],
               data=post_data["data"]
           )
           db.session.add(microblog)
      
       # Add some sample replies to demonstrate the reply system
       db.session.flush()  # Ensure microblogs are saved and have IDs
      
       # Find the JavaScript question post and add a helpful reply
       js_topic = next((t for t in created_topics if "javascript" in t._page_path.lower()), None)
       if js_topic and len(active_users) > 1:
           js_post = MicroBlog.query.filter_by(_topic_id=js_topic.id).first()
           if js_post:
               # Add a helpful reply from a different user
               reply_user = next((u for u in active_users if u.id != js_post._user_id), active_users[0])
               js_post.add_reply(
                   user_id=reply_user.id,
                   reply_content="Try thinking: map transforms, filter selects! Both return arrays but map changes items, filter picks items 💡"
               )
      
       db.session.commit()
       print("Sample microblogs and page topics initialized successfully!")
       print(f"Created {len(created_topics)} page topics and {len(sample_posts)} sample posts:")
       for topic in created_topics:
           post_count = MicroBlog.query.filter_by(_topic_id=topic.id).count()
           print(f"  - {topic._page_path} ({topic._display_name}) - {post_count} posts")

