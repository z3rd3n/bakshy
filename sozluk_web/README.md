# Sözlük - German-English Learning Web Application

A web-based German vocabulary learning application with Gemini API integration and Anki-style spaced repetition flashcards.

## Features

- User registration and authentication
- Gemini API integration for detailed German word information
- Create and manage decks of vocabulary words
- Anki-style flashcard review system with spaced repetition
- Responsive design works on desktop and mobile

## Requirements

- Python 3.7+
- Flask
- SQLAlchemy
- Requests

## Installation

1. Clone this repository or download the source code
2. Install the required dependencies:

```
pip install -r requirements.txt
```

3. Run the application:

```
python -m sozluk_web.app
```

4. Open your browser and navigate to http://localhost:5000

## Usage

1. Register a new account
2. Create a new vocabulary deck
3. Add German-English words to your deck using the Gemini API
4. Study your flashcards using the spaced repetition system

## Gemini API

This application requires a Gemini API key to fetch detailed information about German words. 
You can get a free Gemini API key from Google AI Studio: https://ai.google.dev/

## Notes

This is a basic German learning application similar to Anki but with specialized German language features.
The application stores data in a local SQLite database.