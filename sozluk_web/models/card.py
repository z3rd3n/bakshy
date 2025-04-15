from datetime import datetime
from models import db

class Card(db.Model):
    __tablename__ = 'cards'
    
    id = db.Column(db.Integer, primary_key=True)
    front = db.Column(db.String(255), nullable=False)  # German word
    back = db.Column(db.String(255), nullable=False)   # English translation
    additional_translation = db.Column(db.String(255)) # Translation in user's additional language
    example = db.Column(db.Text)                       # Example sentence in German
    example_translation = db.Column(db.Text)           # Translation of example
    notes = db.Column(db.Text)                         # Extra info like artikel, plural form, etc.
    word_type = db.Column(db.String(50))               # Type of word (noun, verb, adjective, etc.)
    etymology = db.Column(db.Text)                     # Etymology information
    
    # Spaced repetition attributes
    ease_factor = db.Column(db.Float, default=2.5)
    interval = db.Column(db.Integer, default=0)        # Days between reviews
    repetitions = db.Column(db.Integer, default=0)     # Number of times reviewed
    last_reviewed = db.Column(db.DateTime)
    next_review = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck_id = db.Column(db.Integer, db.ForeignKey('decks.id'), nullable=False)
    
    def __repr__(self):
        return f'<Card {self.front}>'
    
    @property
    def is_due(self):
        if self.next_review is None:
            return True
        return datetime.utcnow() >= self.next_review