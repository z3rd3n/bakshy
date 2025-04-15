from datetime import datetime
from models import db

class Deck(db.Model):
    __tablename__ = 'decks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    cards = db.relationship('Card', backref='deck', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Deck {self.name}>'
    
    @property
    def card_count(self):
        return len(self.cards)
    
    @property
    def due_cards_count(self):
        now = datetime.utcnow()
        return sum(1 for card in self.cards if card.next_review is None or card.next_review <= now)