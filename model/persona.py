from __init__ import app, db
from sqlalchemy import JSON
from sqlalchemy.orm import validates
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

# Persona categories - different domains/types of archetypes
PERSONA_CATEGORIES = [
    'student',      # Computer Science student learning archetypes (technologist, scrummer, planner, closer)
    'social',       # Social interest archetypes (gamer, musician, athlete, explorer, foodie, artist)
    'achievement',  # Achievement-oriented archetypes (builder, innovator, competitor, mentor)
    'fantasy'       # Superhero/superpower archetypes (speed, strength, intelligence, flight)
]

class UserPersona(db.Model):
    """
    UserPersona Model
    
    A many-to-many relationship between 'users' and 'personas' tables.
    Tracks user persona selections with weights for matching algorithms.
    
    Attributes:
        user_id (Column): An integer representing the user's unique identifier, a foreign key that references the 'users' table.
        persona_id (Column): An integer representing the persona's unique identifier, a foreign key that references the 'personas' table.
        weight (Column): An integer representing the selection priority (2 for primary, 1 for secondary).
        selected_at (Column): A datetime representing when the persona was selected.
    """
    __tablename__ = 'user_personas'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    persona_id = db.Column(db.Integer, db.ForeignKey('personas.id'), primary_key=True)
    weight = db.Column(db.Integer, default=1, nullable=False)  # 2 = primary, 1 = secondary
    selected_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Junction table relationships: Records transactions linking User and Persona
    # Each UserPersona row records a User-Persona pairing (like a transaction receipt)
    # Overlaps setting silences SQLAlchemy warnings about multiple relationship paths
    user = db.relationship("User", backref=db.backref("user_personas_rel", cascade="all, delete-orphan"), overlaps="personas")
    persona = db.relationship("Persona", backref=db.backref("user_personas_rel", cascade="all, delete-orphan"), overlaps="users")
    
    def __init__(self, user, persona, weight=1):
        self.user = user
        self.persona = persona
        self.weight = weight
        self.selected_at = datetime.now(timezone.utc)

    
    def read(self):
        """Read user persona selection data."""
        return {
            'user_id': self.user_id,
            'uid': self.user.uid,
            'persona_id': self.persona_id,
            'persona_alias': self.persona.alias,
            'weight': self.weight,
            'selected_at': self.selected_at.isoformat() if self.selected_at else None
        }
    
    @staticmethod
    def calculate_team_score(user_personas_list):
        """
        Calculate team compatibility score for classroom team formation.
        Maximizes diversity in student category, similarity in achievement category.
        
        Args:
            user_personas_list: List of lists, where each inner list contains UserPersona objects for one user
            
        Returns:
            float: Team compatibility score (0-100)
        """
        if not user_personas_list or len(user_personas_list) < 2:
            return 0.0
            
        # Extract personas by category for each user
        student_personas = []
        achievement_personas = []
        
        for user_personas in user_personas_list:
            for up in user_personas:
                if up.persona._category == 'student':
                    student_personas.append(up.persona._alias)
                elif up.persona._category == 'achievement':
                    achievement_personas.append(up.persona._alias)
        
        # Calculate diversity score for student personas (want variety)
        student_diversity = len(set(student_personas)) / len(student_personas) if student_personas else 0
        
        # Calculate similarity score for achievement personas (want overlap)
        if achievement_personas:
            from collections import Counter
            achievement_counts = Counter(achievement_personas)
            max_count = max(achievement_counts.values())
            achievement_similarity = max_count / len(achievement_personas)
        else:
            achievement_similarity = 0
        
        # Weighted combination: 40% student diversity + 60% achievement similarity
        team_score = (student_diversity * 0.4 + achievement_similarity * 0.6) * 100
        return round(team_score, 2)
    
    @staticmethod
    def calculate_match_score(user1_personas, user2_personas):
        """
        Calculate compatibility score for social matching/dating.
        Emphasizes overlap in social interests with weight consideration.
        
        Args:
            user1_personas: List of UserPersona objects for user 1
            user2_personas: List of UserPersona objects for user 2
            
        Returns:
            float: Match compatibility score (0-100)
        """
        if not user1_personas or not user2_personas:
            return 0.0
        
        # Extract personas by category with weights
        def get_personas_by_category(personas_list):
            result = {'social': [], 'achievement': [], 'fantasy': []}
            for up in personas_list:
                category = up.persona._category
                if category in result:
                    result[category].append((up.persona._alias, up.weight))
            return result
        
        u1_cats = get_personas_by_category(user1_personas)
        u2_cats = get_personas_by_category(user2_personas)
        
        # Calculate social overlap score (weighted)
        social_score = 0
        u1_social = {alias: weight for alias, weight in u1_cats['social']}
        u2_social = {alias: weight for alias, weight in u2_cats['social']}
        
        for alias in set(u1_social.keys()) & set(u2_social.keys()):
            # Shared personas get points based on combined weight
            social_score += u1_social[alias] + u2_social[alias]
        
        # Normalize social score (max possible: 2 primary matches = 2*2 + 2*2 = 8)
        social_normalized = min(social_score / 8.0, 1.0)
        
        # Calculate achievement overlap
        u1_achievement = {alias for alias, _ in u1_cats['achievement']}
        u2_achievement = {alias for alias, _ in u2_cats['achievement']}
        achievement_overlap = len(u1_achievement & u2_achievement) / max(len(u1_achievement | u2_achievement), 1)
        
        # Calculate fantasy complement (different powers create interesting dynamics)
        u1_fantasy = {alias for alias, _ in u1_cats['fantasy']}
        u2_fantasy = {alias for alias, _ in u2_cats['fantasy']}
        fantasy_complement = 1.0 - (len(u1_fantasy & u2_fantasy) / max(len(u1_fantasy | u2_fantasy), 1))
        
        # Weighted combination: 50% social + 30% fantasy complement + 20% achievement
        match_score = (social_normalized * 0.5 + fantasy_complement * 0.3 + achievement_overlap * 0.2) * 100
        return round(match_score, 2)

class Persona(db.Model):
    __tablename__ = 'personas'

    id = db.Column(db.Integer, primary_key=True)
    _category = db.Column(db.String(32), nullable=False)
    _alias = db.Column(db.String(32), unique=True, nullable=False)
    _bio_map = db.Column(JSON, nullable=False)  # Stores: {'title': str, 'description': str, 'archetype': [], 'personality_type': []}
    _empathy_map = db.Column(JSON, nullable=True)  # Stores: {'says': [], 'thinks': [], 'feels': [], 'does': []}
    
    # Define many-to-many relationship with User model through UserPersona table
    # Overlaps setting silences SQLAlchemy warnings about multiple relationship paths
    # No backref needed as User has its own 'personas' relationship
    users = db.relationship('User', secondary='user_personas', lazy='subquery',
                            overlaps="user_personas_rel,user,personas")    

    def __init__(self, _alias, _category, _bio_map, _empathy_map=None):
        self._alias = _alias
        self._category = _category
        self._bio_map = _bio_map
        self._empathy_map = _empathy_map

    @property
    def alias(self):
        return self._alias
    
    @property
    def category(self):
        return self._category
    
    @property
    def bio_map(self):
        return self._bio_map
    
    @property
    def empathy_map(self):
        return self._empathy_map
    
    def __getattr__(self, name):
        """
        Generic property accessor for _bio_map and _empathy_map keys.
        Allows dot notation access to any field in these maps.
        Examples: persona.title, persona.description, persona.archetype, persona.says, persona.thinks
        This is called only when the attribute is not found through normal lookup.
        """
        if name.startswith('_'):
            # Avoid infinite recursion for private attributes
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        
        # Check bio_map first (title, description, archetype, personality_type)
        if self._bio_map and name in self._bio_map:
            return self._bio_map[name]
        
        # Then check empathy_map (says, thinks, feels, does)
        if self._empathy_map and name in self._empathy_map:
            return self._empathy_map[name]
        
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    @validates('_category')
    def validate_category(self, key, value):
        if value not in PERSONA_CATEGORIES:
            raise ValueError(f"Invalid category '{value}'. Must be one of: {', '.join(PERSONA_CATEGORIES)}")
        return value

    def create(self):
        db.session.add(self)
        db.session.commit()
        return self

    def read(self):
        return {
            "id": self.id,
            "category": self.category,
            "alias": self.alias,
            "bio_map": self.bio_map,
            "empathy_map": self.empathy_map
        }


"""Database Creation and Testing"""

def initPersonas():
    """Initialize persona database with student archetype empathy maps."""
    with app.app_context():
        """Create database and tables"""
        db.create_all()
        
        """Student archetype personas for team matching"""
        
        # Technologist Persona - Indy
        p1 = Persona(
            _alias='indy',
            _category='student',
            _bio_map={
                'title': 'Technologist',
                'description': 'I am a driven CS student who enjoys individual work and tackling the hardest technical challenges. I am motivated by mastery and recognition, and often surprise others with exceptional problem-solving skills. I excel in individual assignments and competitions, but group work can be frustrating, especially when team members are less focused on code or schedules are unclear. Building trust and communication with peers is an ongoing challenge, but when I am engaged, I can elevate the whole project.',
                'archetype': ['Introvert', 'Analytical', 'Independent'],
                'personality_type': ['Ambitious', 'Focused']
            },
            _empathy_map={
                'says': [
                    'Look at this new feature I created.',
                    'I just want to ask you and be sure to get it right.',
                    "Those people can't help me, they don't understand themselves."
                ],
                'thinks': [
                    'Prefers not to seek help from students, perceiving it as a potential slowdown.',
                    'Secretly hopes to be a hero, one who makes the project exceptional.',
                    'Believes the teacher is a valuable resource, but also recognizes the importance of self-driven learning for unlimited potential.'
                ],
                'feels': [
                    'Values individual effort, but is open to building trust and communication with peers.',
                    'Often feels excluded due to language difficulties or social barriers.',
                    'Fears opening up or communicating with others or trusting they will complete tasks correctly.'
                ],
                'does': [
                    'Often wants to come in before or stay after class for preferred individual review or help with Teacher.',
                    "When properly engaged, often surprises others' expectations by solving cognitively challenging problems.",
                    'Typically does well on traditional assignments, like AP exams or practices.',
                    'Can loop or get frustrated on materials they have not been able to grasp, sometimes compounded by not reaching out to peers early.'
                ]
            }
        )
        
        # Scrummer Persona - Salem
        p2 = Persona(
            _alias='salem',
            _category='student',
            _bio_map={
                'title': 'Scrummer',
                'description': 'I am a collaborative learner who grows through teamwork and iteration. I enjoy working in teams, contributing to group success, and learning from others. Seeing my team each day makes me happy and excited to solve problems together. While I thrive in Agile environments, I sometimes find it challenging to show my unique contributions and can be unsure how my individual work impacts my grade, especially when groupthink makes it easy to blend in with the team.',
                'archetype': ['Collaborative', 'Optimistic', 'Team-oriented'],
                'personality_type': ['Agile', 'Growth Mindset']
            },
            _empathy_map={
                'says': [
                    'I like working in teams and collaborating with peers.',
                    "It is OK that we don't get things right as we have iteration opportunities."
                ],
                'thinks': [
                    'Believes in team and has a growth mindset.',
                    'Sometimes is unsure how their individual work impacts their grade in class.'
                ],
                'feels': [
                    'Thinks about solving issues together.',
                    'Hopes to get things done through group effort.',
                    'Feels happy and excited to see team each day.'
                ],
                'does': [
                    'Is engaged in team conversations.',
                    'Is actively involved in Agile Ceremonies.',
                    'Often starts discussing or solving problems before all directions are completed.',
                    'Some scrummers allow the overshadow of team accomplishments to be an excuse for poor individual contribution.'
                ]
            }
        )
        
        # Planner Persona - Phoenix
        p3 = Persona(
            _alias='phoenix',
            _category='student',
            _bio_map={
                'title': 'Planner',
                'description': 'I am an organized CS student who excels at planning, tracking, and communicating with my team. I champion process management and issue tracking, and I am motivated by seeing a comprehensive plan come together. I gain satisfaction from seeing projects that are working and highly functional. Sometimes, I struggle to balance planning with hands-on technical work, especially when there is a lot to organize or integrate.',
                'archetype': ['Organized', 'Detail-oriented', 'Strategic'],
                'personality_type': ['Process Manager', 'Communicator']
            },
            _empathy_map={
                'says': [
                    'It is satisfying seeing something I worked on become useful.',
                    'I have read every detail written with exactness.',
                    'I notice these inconsistencies in requirements.'
                ],
                'thinks': [
                    'Believes a comprehensive plan should incorporate all requirements.',
                    'Thinks they need to read all provided information.',
                    'Desires feedback from team members on accomplishments related to plan.'
                ],
                'feels': [
                    'Feels responsibility for communicating plans with others.',
                    'Hopes that all team members will do their assigned portion of the work.'
                ],
                'does': [
                    'Often a champion of issue tracking and kanban boards.',
                    'Seeks guidance on issues that present barriers or impede progress on the plan.',
                    'Seeks opportunities for the instructor to let them lead larger classroom projects or prepare for seminar activities like AP Testing.',
                    'Sometimes struggles with prioritizing coding, as there is always so much to organize, plan, or integrate.'
                ]
            }
        )
        
        # Closer Persona - Cody
        p4 = Persona(
            _alias='cody',
            _category='student',
            _bio_map={
                'title': 'Closer',
                'description': 'I am a detail-oriented CS student who thrives on completing tasks and meeting milestones. I feel most confident when requirements are clear and feedback is available, and I take pride in finishing work efficiently. While I excel in structured environments, I may hesitate or feel anxious with open-ended assignments. Seeking confirmation from teachers or peers helps me stay on track and achieve success.',
                'archetype': ['Detail-oriented', 'Driven', 'Perfectionist'],
                'personality_type': ['Finisher', 'Reliable']
            },
            _empathy_map={
                'says': [
                    'It makes me happy to finish tasks.',
                    'I listened to your instructions, do you think my idea is OK?',
                    'Here is my work after our last conversation, does it meet the requirements?'
                ],
                'thinks': [
                    'Focuses on how tasks map to requirements.',
                    'Worries about meeting exact grade requirements.',
                    'Thinks of long term success, often beyond classroom (ie career and college).'
                ],
                'feels': [
                    'Hopes to achieve a path to success by obtaining extra assurances.',
                    'Feel confident and satisfied when coding and meeting requirements on vetted issues and meeting milestones.',
                    'Desires to be active collaborator and communicator.'
                ],
                'does': [
                    'Quickly acts on well-defined plans and completes technical work efficiently.',
                    'Regularly meets personal and project milestones.',
                    'Seeks to be first in line for preliminary reviews, but will trend toward back of line on summative reviews.',
                    'Seeks confirmation from teachers or peers before moving on to the next task.',
                    'May get stuck or hesitate when faced with open-ended or creative assignments.'
                ]
            }
        )
        
        """Social interest personas for teen engagement"""
        
        # Gamer Persona
        s1 = Persona(
            _alias='pixel',
            _category='social',
            _bio_map={
                'title': 'Gamer',
                'description': 'I live for the rush of competition and the thrill of leveling up. Gaming is where I connect with friends, strategize, and express myself. Whether it\'s esports, RPGs, or casual mobile games, I find community and purpose in virtual worlds.',
                'archetype': ['Competitive', 'Strategic', 'Connected'],
                'personality_type': ['Team Player', 'Problem Solver']
            },
            _empathy_map={
                'says': ['Did you see that clutch play?', 'We should squad up later.', 'I just hit Diamond rank!'],
                'thinks': ['Gaming teaches real skills like teamwork and quick thinking.', 'My online friends understand me better than most IRL people.'],
                'feels': ['Most alive when in the zone during intense matches.', 'Frustrated when people dismiss gaming as just entertainment.'],
                'does': ['Streams gameplay or watches Twitch/YouTube gaming content.', 'Analyzes strategies and optimizes character builds.', 'Coordinates with teammates across time zones.']
            }
        )
        
        # Musician Persona
        s2 = Persona(
            _alias='cadence',
            _category='social',
            _bio_map={
                'title': 'Musician',
                'description': 'Music is my language and my escape. I express emotions through sound, whether creating beats, playing instruments, or curating the perfect playlist. Music connects me to culture, identity, and community in ways words cannot.',
                'archetype': ['Creative', 'Expressive', 'Passionate'],
                'personality_type': ['Artist', 'Connector']
            },
            _empathy_map={
                'says': ['This song perfectly captures the vibe.', 'Want to hear what I\'ve been working on?', 'Music is everything to me.'],
                'thinks': ['Different genres reflect different parts of my identity.', 'Creating music is how I process my feelings.'],
                'feels': ['Energized by discovering new artists and sounds.', 'Vulnerable when sharing original work with others.'],
                'does': ['Spends hours perfecting a track or practicing an instrument.', 'Makes playlists for every mood and occasion.', 'Attends concerts and connects with other musicians online.']
            }
        )
        
        # Athlete Persona
        s3 = Persona(
            _alias='ace',
            _category='social',
            _bio_map={
                'title': 'Athlete',
                'description': 'I thrive on movement, competition, and pushing my physical limits. Fitness isn\'t just exercise—it\'s discipline, confidence, and mental health. Whether team sports or solo workouts, I find strength in the grind and community in shared goals.',
                'archetype': ['Driven', 'Disciplined', 'Energetic'],
                'personality_type': ['Leader', 'Motivator']
            },
            _empathy_map={
                'says': ['No pain, no gain.', 'Let\'s hit the gym together.', 'I PR\'d today!'],
                'thinks': ['Physical strength builds mental resilience.', 'My routine keeps me grounded and focused.'],
                'feels': ['Accomplished after a tough workout or game.', 'Restless when unable to train or compete.'],
                'does': ['Tracks progress with fitness apps and sets measurable goals.', 'Encourages friends to join workouts or sports.', 'Follows athletes and fitness influencers for inspiration.']
            }
        )
        
        # Explorer Persona
        s4 = Persona(
            _alias='marco',
            _category='social',
            _bio_map={
                'title': 'Explorer',
                'description': 'I crave new experiences, cultures, and perspectives. Travel and adventure feed my curiosity about the world. Even locally, I seek hidden gems, try new foods, and collect stories that broaden my understanding of life.',
                'archetype': ['Curious', 'Adventurous', 'Open-minded'],
                'personality_type': ['Seeker', 'Storyteller']
            },
            _empathy_map={
                'says': ['I need to visit there someday.', 'Let\'s try that new place downtown.', 'Travel changes you.'],
                'thinks': ['Every place has a story worth discovering.', 'Comfort zones are meant to be expanded.'],
                'feels': ['Alive when exploring somewhere new.', 'Inspired by different cultures and perspectives.'],
                'does': ['Plans trips and researches destinations obsessively.', 'Documents experiences through photos and journals.', 'Seeks out diverse foods, events, and communities.']
            }
        )
        
        """Achievement-oriented personas for goal-driven matching"""
        
        # Scholar Persona
        a1 = Persona(
            _alias='libra',
            _category='achievement',
            _bio_map={
                'title': 'Scholar',
                'description': 'I am driven by academic excellence and preparing for my future. AP exams, SAT/ACT scores, and college admissions define my success. I take challenging courses, maintain a high GPA, and constantly think about how my achievements will shape my college applications and career path.',
                'archetype': ['Disciplined', 'Goal-oriented', 'Achievement-focused'],
                'personality_type': ['Academic', 'Future-minded']
            },
            _empathy_map={
                'says': ['What AP classes are you taking?', 'I need a 5 on this exam.', 'This will look good on my college application.'],
                'thinks': ['Every grade matters for my transcript.', 'I need to stand out in the college admissions process.', 'Test scores can open doors to better opportunities.'],
                'feels': ['Anxious about test performance and college acceptance.', 'Proud when academic hard work pays off.', 'Pressure to maintain excellence across all subjects.'],
                'does': ['Studies rigorously for AP exams and standardized tests.', 'Researches colleges and scholarship opportunities constantly.', 'Takes the most challenging course load possible.', 'Seeks academic recognition through honor societies and awards.']
            }
        )
        
        # Competitor Persona
        a2 = Persona(
            _alias='nikola',
            _category='achievement',
            _bio_map={
                'title': 'Competitor',
                'description': 'I thrive in competitive environments and love the rush of tournaments and competitions. Whether it\'s robotics, CyberPatriots, DECA, or hackathons, I\'m driven by the challenge of testing my skills against others. Winning trophies, medals, and recognition fuels my passion.',
                'archetype': ['Competitive', 'Team-focused', 'Strategic'],
                'personality_type': ['Winner', 'Performer']
            },
            _empathy_map={
                'says': ['Our team is going to nationals!', 'We placed first in regionals!', 'I want to compete at the highest level.'],
                'thinks': ['Competition brings out my best performance.', 'Team victories are sweeter than individual wins.', 'Preparation and practice lead to championship results.'],
                'feels': ['Energized by competition pressure and high stakes.', 'Proud representing my school at tournaments.', 'Driven to improve after every competition.'],
                'does': ['Joins competitive clubs like robotics, CyberPatriots, DECA, Science Olympiad.', 'Practices intensely before competitions and tournaments.', 'Analyzes competitor strategies to gain an edge.', 'Celebrates team victories and learns from defeats.']
            }
        )
        
        # Builder Persona
        a3 = Persona(
            _alias='isaac',
            _category='achievement',
            _bio_map={
                'title': 'Builder',
                'description': 'I create tangible things that work and matter. Whether coding apps, building robots, designing products, or crafting solutions, I love bringing ideas to life. My hands-on approach and maker mindset drive me to build, test, and iterate until it works perfectly.',
                'archetype': ['Practical', 'Hands-on', 'Creative'],
                'personality_type': ['Maker', 'Engineer']
            },
            _empathy_map={
                'says': ['Let me build a prototype.', 'I can make that work.', 'Look what I created!'],
                'thinks': ['Building is the best way to learn.', 'Real projects are more valuable than theoretical work.', 'Seeing my creations in action is the ultimate reward.'],
                'feels': ['Satisfied when projects come to life.', 'Excited by technical challenges and problem-solving.', 'Frustrated when stuck on implementation details.'],
                'does': ['Builds projects, apps, robots, and physical creations.', 'Joins maker clubs, robotics teams, and engineering groups.', 'Shares creations on GitHub, maker fairs, and competitions.', 'Learns new tools and technologies through hands-on experimentation.']
            }
        )
        
        # Ambassador Persona
        a4 = Persona(
            _alias='madam',
            _category='achievement',
            _bio_map={
                'title': 'Ambassador',
                'description': 'I find purpose in serving my community and making a difference beyond myself. Whether tutoring younger students, advocating for social justice, volunteering at elementary schools, or leading service projects, I measure success by the positive impact I create in others\' lives.',
                'archetype': ['Service-oriented', 'Compassionate', 'Leader'],
                'personality_type': ['Advocate', 'Mentor']
            },
            _empathy_map={
                'says': ['How can we help our community?', 'I\'m tutoring elementary kids this weekend.', 'We need to make a difference.'],
                'thinks': ['Service to others gives my life meaning.', 'Education and opportunity should be accessible to everyone.', 'Small acts of kindness create ripple effects.'],
                'feels': ['Fulfilled when helping others succeed and grow.', 'Passionate about social justice and equity issues.', 'Connected to community through service work.'],
                'does': ['Volunteers regularly at elementary schools or community centers.', 'Tutors and mentors younger students in STEM or other subjects.', 'Joins service clubs focused on social justice and community impact.', 'Organizes fundraisers, awareness campaigns, and service projects.']
            }
        )
        
        """Fantasy superpower personas for aspirational matching"""
        
        # Speed Persona
        f1 = Persona(
            _alias='flash',
            _category='fantasy',
            _bio_map={
                'title': 'Speedster',
                'description': 'If I had a superpower, it would be super speed—getting things done fast, responding instantly, and never wasting time. I value efficiency, quick thinking, and staying ahead of the curve.',
                'archetype': ['Fast-paced', 'Responsive', 'Efficient'],
                'personality_type': ['Executor', 'Quick-thinker']
            },
            _empathy_map={
                'says': ['Let\'s move quickly on this.', 'Time is precious.', 'I already finished that.'],
                'thinks': ['Speed and momentum create success.', 'Waiting around wastes opportunity.'],
                'feels': ['Energized by rapid progress and quick wins.', 'Impatient with slow processes or delays.'],
                'does': ['Completes tasks ahead of deadlines.', 'Multitasks and context-switches rapidly.', 'Optimizes workflows for maximum efficiency.']
            }
        )
        
        # Strength Persona
        f2 = Persona(
            _alias='parker',
            _category='fantasy',
            _bio_map={
                'title': 'Powerhouse',
                'description': 'If I had a superpower, it would be super strength—the ability to tackle the hardest challenges, carry heavy loads, and power through obstacles. I value resilience, determination, and raw capability.',
                'archetype': ['Resilient', 'Powerful', 'Unstoppable'],
                'personality_type': ['Force', 'Perseverer']
            },
            _empathy_map={
                'says': ['I can handle the tough stuff.', 'Bring on the challenge.', 'I don\'t give up easily.'],
                'thinks': ['Strength comes from persistence and grit.', 'The hardest problems are the most rewarding.'],
                'feels': ['Confident tackling difficult tasks others avoid.', 'Energized by overcoming major obstacles.'],
                'does': ['Volunteers for the most challenging assignments.', 'Pushes through setbacks with determination.', 'Supports teammates who need heavy lifting.']
            }
        )
        
        # Intelligence Persona
        f3 = Persona(
            _alias='merlin',
            _category='fantasy',
            _bio_map={
                'title': 'Mastermind',
                'description': 'If I had a superpower, it would be super intelligence—solving complex problems, seeing patterns others miss, and mastering any subject. I value knowledge, strategy, and intellectual excellence.',
                'archetype': ['Analytical', 'Strategic', 'Intellectual'],
                'personality_type': ['Thinker', 'Strategist']
            },
            _empathy_map={
                'says': ['Let me analyze this first.', 'I see a pattern here.', 'Knowledge is power.'],
                'thinks': ['Deep understanding beats surface-level knowing.', 'Strategic thinking prevents future problems.'],
                'feels': ['Excited by intellectual puzzles and complex systems.', 'Frustrated by illogical approaches or ignorance.'],
                'does': ['Researches thoroughly before making decisions.', 'Develops sophisticated strategies and plans.', 'Masters new concepts quickly through intense study.']
            }
        )
        
        # Flight Persona
        f4 = Persona(
            _alias='sky',
            _category='fantasy',
            _bio_map={
                'title': 'Visionary',
                'description': 'If I had a superpower, it would be flight—seeing the big picture from above, rising above limitations, and reaching new heights. I value perspective, freedom, and boundless possibility.',
                'archetype': ['Big-picture', 'Optimistic', 'Limitless'],
                'personality_type': ['Dreamer', 'Inspirer']
            },
            _empathy_map={
                'says': ['Imagine the possibilities.', 'Let\'s aim higher.', 'The sky\'s not the limit.'],
                'thinks': ['Perspective changes everything.', 'Limitations are often self-imposed.'],
                'feels': ['Inspired by ambitious visions and bold goals.', 'Confined by narrow thinking or small dreams.'],
                'does': ['Sets audacious goals that inspire others.', 'Sees connections across different domains.', 'Encourages teams to think beyond constraints.']
            }
        )
        
        personas = [p1, p2, p3, p4, s1, s2, s3, s4, a1, a2, a3, a4, f1, f2, f3, f4]
        
        for persona in personas:
            try:
                persona.create()
                print(f"Created persona: {persona.title} ({persona._alias}) - {persona._category}")
            except IntegrityError:
                db.session.rollback()
                print(f"Persona already exists: {persona._alias}")


def initPersonaUsers():
    """
    Create test users based on persona aliases and assign them persona attributes.
    Each user gets their namesake persona plus random selections from other categories.
    """
    import random
    from model.user import User
    
    with app.app_context():
        """Ensure personas exist first"""
        db.create_all()
        
        # Get all personas organized by category
        personas_by_category = {
            'student': Persona.query.filter_by(_category='student').all(),
            'social': Persona.query.filter_by(_category='social').all(),
            'achievement': Persona.query.filter_by(_category='achievement').all(),
            'fantasy': Persona.query.filter_by(_category='fantasy').all()
        }
        
        # Get all personas for iteration
        all_personas = Persona.query.all()
        
        for persona in all_personas:
            # Create user with persona alias as uid
            user = User(
                name=persona._alias.capitalize() + " " + persona._bio_map.get('title', ''),
                uid=persona._alias,
                password=app.config["DEFAULT_PASSWORD"],
                role="User"
            )
            
            try:
                user.create()
                print(f"Created user: {user.name} ({user.uid})")
                
                # Now assign personas to this user
                user_persona_selections = []
                
                # Assign the user their namesake persona (primary identity)
                namesake_category = persona._category
                namesake_up = UserPersona(user=user, persona=persona, weight=2)
                user_persona_selections.append(namesake_up)
                
                # Assign personas from other categories based on selection rules
                for category, personas_list in personas_by_category.items():
                    if category == namesake_category:
                        continue  # Skip their primary category (already assigned)
                    
                    if category == 'social':
                        # Social: Pick 2 (1 primary weight=2, 1 secondary weight=1)
                        if len(personas_list) >= 2:
                            social_picks = random.sample(personas_list, 2)
                            user_persona_selections.append(UserPersona(user=user, persona=social_picks[0], weight=2))
                            user_persona_selections.append(UserPersona(user=user, persona=social_picks[1], weight=1))
                        elif len(personas_list) == 1:
                            user_persona_selections.append(UserPersona(user=user, persona=personas_list[0], weight=2))
                    else:
                        # Student, Achievement, Fantasy: Pick 1 (weight=1)
                        if personas_list:
                            random_pick = random.choice(personas_list)
                            user_persona_selections.append(UserPersona(user=user, persona=random_pick, weight=1))
                
                # Add all UserPersona relationships to the user
                for up in user_persona_selections:
                    up.user_id = user.id
                    db.session.add(up)
                
                db.session.commit()
                
                # Print summary of assigned personas
                persona_summary = [f"{up.persona._bio_map.get('title', '')} (w={up.weight})" for up in user_persona_selections]
                print(f"  Assigned personas: {', '.join(persona_summary)}")
                
            except IntegrityError:
                db.session.rollback()
                print(f"User already exists: {persona._alias}")
            except Exception as e:
                db.session.rollback()
                print(f"Error creating user {persona._alias}: {e}")
