Music Flashcard App

A Django-based web app that combines spaced repetition learning with music data integration to create interactive flashcards.

Features:
User authentication (register, login, logout)
Flashcard set CRUD + saving/sharing
SM-2 spaced repetition study system
Study analytics with Chart.js
Music-based flashcard generation using:
Last.fm (track metadata)
YouTube (video playback)

Tech Stack
Django (Python)
HTML/CSS/JavaScript
Chart.js
SQLite

Status
Core flashcard + study system complete
API integrations implemented
Music generation flow built but partially untested (API quota limits)

Highlights
Implemented SM-2 spaced repetition algorithm
Designed API pipeline: Last.fm → YouTube → flashcards
Refactored into clean service-oriented architecture
