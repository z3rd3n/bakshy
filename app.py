from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json
import re
import os
import uuid
import datetime
from functools import wraps

# Import db from models/__init__.py
from models import db
# Import models after db initialization to avoid circular imports
from models.user import User
from models.deck import Deck
from models.card import Card

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key-replace-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sozluk.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the db with the app
db.init_app(app)

# Gemini API integration
def query_gemini(word, api_key, additional_language=None):
    GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    # Add the additional language to the prompt if provided
    additional_language_prompt = ""
    if additional_language:
        additional_language_prompt = f"\n13. **additional_translation**: Translation in {additional_language}"
    
    prompt = (
        f"You are a helpful German language assistant. For the word: **{word}**, provide the following structured information.\n"
        "If the word is not a valid German word, return this JSON exactly:\n"
        "{\"error\": \"Not a valid German word\"}\n\n"
        "1. **base_d**: The original German word\n"
        "2. **base_e**: The English translation(s)\n"
        "3. **artikel_d**: The definite article if the word is a noun (e.g., \"der\", \"die\", \"das\"). Leave empty if not a noun.\n"
        "4. **plural_d**: The plural form (for nouns). Leave empty if not a noun.\n"
        "5. **praesens**: Present tense (3rd person singular), e.g., \"läuft\"\n"
        "6. **praeteritum**: Simple past tense (3rd person singular), e.g., \"lief\"\n"
        "7. **perfekt**: Present perfect form, e.g., \"ist gelaufen\"\n"
        "8. **full_d**: A combined string of the above three conjugation forms, e.g., \"läuft, lief, ist gelaufen\"\n"
        "9. **s1**: A natural German sentence using the word.\n"
        "10. **s1e**: English translation of the first sentence.\n"
        "11. **s2**: A second sentence only if the word has a different context.\n"
        "12. **s2e**: English translation of the second sentence.\n"
        "13. **word_type**: The type of word (noun, verb, adjective, adverb, preposition, etc.).\n"
        "14. **etymology**: A brief explanation of the word's origin and etymology."
        f"{additional_language_prompt}\n\n"
        "Example:\n"
        "```json\n"
        "{\n"
        "  \"base_d\": \"laufen\",\n"
        "  \"base_e\": \"to run\",\n"
        "  \"artikel_d\": \"\",\n"
        "  \"plural_d\": \"\",\n"
        "  \"praesens\": \"läuft\",\n"
        "  \"praeteritum\": \"lief\",\n"
        "  \"perfekt\": \"ist gelaufen\",\n"
        "  \"full_d\": \"läuft, lief, ist gelaufen\",\n"
        "  \"s1\": \"Ich laufe jeden Morgen im Park.\",\n"
        "  \"s1e\": \"I run every morning in the park.\",\n"
        "  \"s2\": \"Er läuft zur Arbeit, weil er den Bus verpasst hat.\",\n"
        "  \"s2e\": \"He runs to work because he missed the bus.\",\n"
        "  \"word_type\": \"verb\",\n"
        "  \"etymology\": \"From Middle High German 'loufen', Old High German 'loufan'. Related to English 'leap'.\""
        + (f",\n  \"additional_translation\": \"correr\"" if additional_language else "") + 
        "\n}\n"
        "```"
    )

    headers = {'Content-Type': 'application/json'}
    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        response = requests.post(GEMINI_ENDPOINT, headers=headers, json=body)
        result = response.json()
        if "candidates" not in result:
            return {"error": f"Gemini error: {result.get('error', 'No candidates returned')}"}
        content = result["candidates"][0]["content"]["parts"][0]["text"]

        match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
        if not match:
            raise ValueError("JSON block not found.")
        parsed = json.loads(match.group(1))

        # Ensure fields are properly populated
        if "error" in parsed:
            return parsed

        # Process and clean up the data
        if not parsed.get("full_d"):
            praesens = parsed.get("praesens", "").strip()
            praeteritum = parsed.get("praeteritum", "").strip()
            perfekt = parsed.get("perfekt", "").strip()

            if praesens or praeteritum or perfekt:
                parsed["full_d"] = ", ".join(filter(None, [praesens, praeteritum, perfekt]))
            elif parsed.get("artikel_d") and parsed.get("base_d"):
                parsed["full_d"] = f"{parsed['artikel_d'].strip()} {parsed['base_d'].strip()}"
            else:
                parsed["full_d"] = parsed.get("base_d", "")

        return parsed

    except Exception as e:
        return {"error": str(e)}

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        return redirect(url_for('search'))
    
    # For GET requests, just display the search form
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([username, email, password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
            
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists', 'error')
            return render_template('register.html')
            
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already in use', 'error')
            return render_template('register.html')
        
        # Create user
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # Create default deck for new user
        default_deck = Deck(
            name="My First Deck",
            description="Default deck for German vocabulary",
            user_id=new_user.id
        )
        
        db.session.add(default_deck)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Invalid username or password', 'error')
            return render_template('login.html')
        
        # Set session
        session['user_id'] = user.id
        session['username'] = user.username
        
        flash('Login successful!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session.get('user_id')
    decks = Deck.query.filter_by(user_id=user_id).all()
    return render_template('dashboard.html', decks=decks)

@app.route('/deck/create', methods=['GET', 'POST'])
@login_required
def create_deck():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        if not name:
            flash('Deck name is required', 'error')
            return render_template('create_deck.html')
        
        # Create deck
        new_deck = Deck(
            name=name,
            description=description,
            user_id=session.get('user_id')
        )
        
        db.session.add(new_deck)
        db.session.commit()
        
        flash('Deck created successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('create_deck.html')

@app.route('/deck/<int:deck_id>')
@login_required
def view_deck(deck_id):
    deck = db.session.get(Deck, deck_id)
    if not deck:
        abort(404)
    
    # Make sure the deck belongs to the user
    if deck.user_id != session.get('user_id'):
        flash('You do not have permission to view this deck', 'error')
        return redirect(url_for('dashboard'))
    
    # Get the current user for preference settings
    current_user = db.session.get(User, session.get('user_id'))
    
    cards = Card.query.filter_by(deck_id=deck_id).all()
    return render_template('view_deck.html', deck=deck, cards=cards, current_user=current_user)

@app.route('/deck/<int:deck_id>/add', methods=['GET', 'POST'])
@login_required
def add_words(deck_id):
    deck = db.session.get(Deck, deck_id)
    if not deck:
        abort(404)
        
    # Make sure the deck belongs to the user
    if deck.user_id != session.get('user_id'):
        flash('You do not have permission to modify this deck', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        words_raw = request.form.get('words', '')
        api_key = request.form.get('api_key', '')
        additional_language = request.form.get('additional_language', None)
        
        if not api_key:
            flash('Gemini API key is required', 'error')
            return render_template('add_words.html', deck=deck)
        
        words = re.split(r"[,\n]", words_raw)
        words = [w.strip() for w in words if w.strip()]
        
        if not words:
            flash('Please enter at least one word', 'error')
            return render_template('add_words.html', deck=deck)
        
        results = []
        
        for word in words:
            # Query Gemini API for word data
            word_data = query_gemini(word, api_key, additional_language)
            
            if 'error' in word_data:
                results.append({
                    'word': word,
                    'status': 'error',
                    'message': word_data['error']
                })
                continue
            
            # Create card
            new_card = Card(
                front=word_data.get('base_d', word),
                back=word_data.get('base_e', ''),
                additional_translation=word_data.get('additional_translation', ''),
                example=word_data.get('s1', ''),
                example_translation=word_data.get('s1e', ''),
                word_type=word_data.get('word_type', ''),
                etymology=word_data.get('etymology', ''),
                notes=', '.join(filter(None, [
                    word_data.get('artikel_d', ''),
                    word_data.get('plural_d', ''),
                    word_data.get('full_d', '')
                ])),
                deck_id=deck_id
            )
            
            db.session.add(new_card)
            
            results.append({
                'word': word_data.get('base_d', word),
                'status': 'success',
                'translation': word_data.get('base_e', '')
            })
        
        db.session.commit()
        
        return render_template('add_words_results.html', deck=deck, results=results)
    
    return render_template('add_words.html', deck=deck)

@app.route('/deck/<int:deck_id>/study')
@login_required
def study_deck(deck_id):
    deck = db.session.get(Deck, deck_id)
    if not deck:
        abort(404)
    
    # Make sure the deck belongs to the user
    if deck.user_id != session.get('user_id'):
        flash('You do not have permission to study this deck', 'error')
        return redirect(url_for('dashboard'))
    
    # Get the current user for preference settings
    current_user = db.session.get(User, session.get('user_id'))
    
    # Create a serializable dictionary with only the user preferences we need
    user_preferences = {
        'show_etymology': current_user.show_etymology,
        'show_additional_language': current_user.show_additional_language,
        'additional_language': current_user.additional_language
    }
    
    cards_query = Card.query.filter_by(deck_id=deck_id).all()
    
    if not cards_query:
        flash('This deck has no cards to study', 'info')
        return redirect(url_for('view_deck', deck_id=deck_id))
    
    # Convert Card objects to dictionaries for JSON serialization
    cards = []
    for card in cards_query:
        cards.append({
            'id': card.id,
            'front': card.front,
            'back': card.back,
            'additional_translation': card.additional_translation,
            'example': card.example,
            'example_translation': card.example_translation,
            'notes': card.notes,
            'word_type': card.word_type,
            'etymology': card.etymology,
            'is_due': card.is_due
        })
    
    return render_template('study_deck.html', deck=deck, cards=cards, user_preferences=user_preferences)

@app.route('/card/<int:card_id>/update', methods=['POST'])
@login_required
def update_card(card_id):
    card = db.session.get(Card, card_id)
    deck = db.session.get(Deck, card.deck_id)
    if not deck:
        return jsonify({'status': 'error', 'message': 'Deck not found'}), 404
    
    # Make sure the deck belongs to the user
    if deck.user_id != session.get('user_id'):
        return jsonify({'status': 'error', 'message': 'Permission denied'}), 403
    
    # Update review statistics
    quality = int(request.form.get('quality', 0))  # 0-5 quality rating
    
    # Simplified spaced repetition algorithm
    if quality < 3:
        # Failed recall - reset interval
        card.interval = 1
    else:
        # Successful recall - increase interval
        if card.interval == 0:
            card.interval = 1
        else:
            card.interval = card.interval * (1 + (quality - 2) * 0.1) # Gradual increase based on quality
    
    card.last_reviewed = datetime.datetime.now()
    card.next_review = datetime.datetime.now() + datetime.timedelta(days=card.interval)
    
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'interval': card.interval,
        'next_review': card.next_review.strftime('%Y-%m-%d')
    })

@app.route('/card/<int:card_id>/delete', methods=['POST'])
@login_required
def delete_card(card_id):
    try:
        # Get the card using db.session.get() - SQLAlchemy 2.0 compatible approach
        card = db.session.get(Card, card_id)
        if not card:
            return jsonify({'status': 'error', 'message': 'Card not found or already deleted.'}), 404

        # Get the deck
        deck = db.session.get(Deck, card.deck_id)

        # Make sure the deck exists and belongs to the user
        if not deck or deck.user_id != session.get('user_id'):
            return jsonify({'status': 'error', 'message': 'Permission denied'}), 403

        # Delete the card
        db.session.delete(card)
        db.session.commit()

        return jsonify({'status': 'success'})
    except Exception as e:
        # Log the error for debugging
        app.logger.error(f"Error deleting card {card_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'An unexpected error occurred. Please try again later.'}), 500

@app.route('/deck/<int:deck_id>/delete', methods=['POST'])
@login_required
def delete_deck(deck_id):
    deck = db.session.get(Deck, deck_id)
    if not deck:
        flash('Deck not found', 'error')
        return redirect(url_for('dashboard'))
    
    # Make sure the deck belongs to the user
    if deck.user_id != session.get('user_id'):
        flash('You do not have permission to delete this deck', 'error')
        return redirect(url_for('dashboard'))
    
    # Get deck name to display in success message
    deck_name = deck.name
    
    # Delete the deck (related cards will be deleted automatically due to cascade)
    db.session.delete(deck)
    db.session.commit()
    
    flash(f'Deck "{deck_name}" has been deleted successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/api/search', methods=['POST'])
@login_required
def search_word():
    word = request.form.get('word')
    api_key = request.form.get('api_key')
    additional_language = request.form.get('additional_language', None)
    
    if not word or not api_key:
        return jsonify({'status': 'error', 'message': 'Word and API key are required'}), 400
    
    result = query_gemini(word, api_key, additional_language)
    return jsonify(result)

@app.route('/search', methods=['GET', 'POST'])
def search():
    search_term = request.form.get('search_term', '') if request.method == 'POST' else request.args.get('search_term', '')
    error_message = None
    word_data = None
    search_attempted = False
    decks = []
    
    if search_term:
        search_attempted = True
        user_id = session.get('user_id')
        
        # Get API key - either from user profile if logged in or from form
        api_key = None
        additional_language = None
        if user_id:
            user = db.session.get(User, user_id)
            api_key = user.api_key
            additional_language = user.additional_language
            
            # Get user's decks for the "Add to Deck" feature
            decks = Deck.query.filter_by(user_id=user_id).all()
        
        # Use the API key from file for demo purposes if not logged in or no API key set
        if not api_key:
            try:
                with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api.txt'), 'r') as f:
                    api_key = f.read().strip()
            except:
                error_message = "No API key available. Please log in and set your API key in your profile."
        
        if api_key and not error_message:
            # Query Gemini API for word data
            word_data = query_gemini(search_term, api_key, additional_language)
            
            if 'error' in word_data:
                error_message = word_data['error']
                word_data = None
    
    return render_template('index.html', 
                          search_term=search_term,
                          word_data=word_data,
                          error_message=error_message,
                          search_attempted=search_attempted,
                          decks=decks)

@app.route('/add_to_deck', methods=['POST'])
@login_required
def add_to_deck():
    deck_id = request.form.get('deck_id')
    word_data_json = request.form.get('word_data')
    
    if not deck_id or not word_data_json:
        flash('Missing required parameters', 'error')
        return redirect(url_for('index'))
    
    try:
        word_data = json.loads(word_data_json)
        
        # Verify deck belongs to user
        deck = db.session.get(Deck, deck_id)
        if deck.user_id != session.get('user_id'):
            flash('You do not have permission to add to this deck', 'error')
            return redirect(url_for('index'))
        
        # Create card
        new_card = Card(
            front=word_data.get('base_d', ''),
            back=word_data.get('base_e', ''),
            additional_translation=word_data.get('additional_translation', ''),
            example=word_data.get('s1', ''),
            example_translation=word_data.get('s1e', ''),
            word_type=word_data.get('word_type', ''),
            etymology=word_data.get('etymology', ''),
            notes=', '.join(filter(None, [
                word_data.get('artikel_d', ''),
                word_data.get('plural_d', ''),
                word_data.get('full_d', '')
            ])),
            deck_id=deck_id
        )
        
        db.session.add(new_card)
        db.session.commit()
        
        flash(f'"{word_data.get("base_d")}" added to your deck successfully!', 'success')
        
    except Exception as e:
        flash(f'Error adding word to deck: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = db.session.get(User, session.get('user_id'))
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        additional_language = request.form.get('additional_language')
        show_etymology = 'show_etymology' in request.form
        show_additional_language = 'show_additional_language' in request.form
        
        user.api_key = api_key
        user.additional_language = additional_language
        user.show_etymology = show_etymology
        user.show_additional_language = show_additional_language
        
        db.session.commit()
        flash('Profile settings saved successfully', 'success')
        
        return redirect(url_for('profile'))
    
    return render_template('profile.html', user=user)

@app.route('/statistics')
@login_required
def statistics():
    user_id = session.get('user_id')
    user = db.session.get(User, user_id)
    
    # Get all decks for the user
    decks = Deck.query.filter_by(user_id=user_id).all()
    
    # Collect statistics for each deck
    deck_stats = []
    total_cards = 0
    total_reviews = 0
    cards_due_today = 0
    cards_mastered = 0
    
    for deck in decks:
        # Get all cards in the deck
        cards = Card.query.filter_by(deck_id=deck.id).all()
        
        # Count cards and calculate statistics
        deck_card_count = len(cards)
        deck_reviews = sum(card.repetitions for card in cards)
        deck_due_today = sum(1 for card in cards if card.is_due)
        deck_mastered = sum(1 for card in cards if card.interval >= 30)  # Cards with 30+ day interval
        
        # Add deck stats to the list
        deck_stats.append({
            'id': deck.id,
            'name': deck.name,
            'card_count': deck_card_count,
            'reviews': deck_reviews,
            'due_today': deck_due_today,
            'mastered': deck_mastered
        })
        
        # Add to totals
        total_cards += deck_card_count
        total_reviews += deck_reviews
        cards_due_today += deck_due_today
        cards_mastered += deck_mastered
    
    # Calculate percentages for mastery
    mastery_percentage = 0
    if total_cards > 0:
        mastery_percentage = (cards_mastered / total_cards) * 100
    
    # Get cards reviewed by date for the last 30 days
    today = datetime.datetime.now().date()
    start_date = today - datetime.timedelta(days=29)
    
    # Query all cards with last_reviewed within the last 30 days
    reviewed_cards = Card.query.join(Deck).filter(
        Card.last_reviewed.isnot(None),
        Card.last_reviewed >= start_date,
        Deck.user_id == user_id
    ).all()
    
    # Count cards reviewed per day
    daily_reviews = {}
    for i in range(30):
        date = (today - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
        daily_reviews[date] = 0
    
    for card in reviewed_cards:
        review_date = card.last_reviewed.date().strftime('%Y-%m-%d')
        if review_date in daily_reviews:
            daily_reviews[review_date] += 1
    
    # Sort by date (chronological order)
    daily_reviews_sorted = [(date, count) for date, count in daily_reviews.items()]
    daily_reviews_sorted.sort(key=lambda x: x[0])
    
    return render_template(
        'statistics.html',
        deck_stats=deck_stats,
        total_cards=total_cards,
        total_reviews=total_reviews,
        cards_due_today=cards_due_today,
        cards_mastered=cards_mastered,
        mastery_percentage=mastery_percentage,
        daily_reviews=daily_reviews_sorted
    )

# Initialize database tables
def init_db():
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)