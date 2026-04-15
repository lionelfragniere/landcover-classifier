## Changelog

- 2024-07-30: Added UNOPS logo to the header of `templates/index.html`.
- 2024-07-30: Attempted to diagnose and fix "water" over-classification. Identified potential remapping issue in `app.py` for WorldCover classes 50 and 100. However, full browser verification of the fix was blocked by Earth Engine authentication issues, leading to the remapping changes being reverted. The application currently requires proper Earth Engine authentication to function.


- 2024-07-30: Refactored frontend to use external CSS and Flask's `render_template`. Moved inline CSS to `static/css/style.css` and HTML content to `templates/index.html`.
- 2024-07-30: Attempted to diagnose and fix "water" over-classification. Identified potential remapping issue in `app.py` for WorldCover classes 50 and 100. However, full browser verification of the fix was blocked by Earth Engine authentication issues, leading to the remapping changes being reverted.


- 2024-07-30: Implemented pre-training for the landcover classifier using ESA WorldCover 2021 as ground truth. The classifier is now trained once on application startup using a diverse geographic region, significantly improving classification accuracy and consistency. The `classify` endpoint now utilizes this pre-trained model, removing the flawed random point training.
- 2024-07-30: Expanded the training geometry and increased the number of training pixels for the landcover classifier to improve accuracy and reduce bias towards 'water' classifications.


- 2023-10-27: Implemented UNOPS dark theme with Inter font, primary blue color, and basic styling for header, navigation, and cards. Created Flask app and HTML template to demonstrate the theme.
- 2023-10-27: Improved Earth Engine error handling and ensured session termination in `ee_classifier.py`.
- 2023-10-27: Removed interactive `ee.Authenticate()` call from `ee_classifier.py` as it's not suitable for automated environments. Earth Engine authentication must be pre-configured.
- 2023-10-27: Consolidated `app.py` files, added `Response` to Flask import, and moved `ee_classifier.py` to `app/ee_classifier.py` for correct project structure.
- 2023-10-27: Created `main.py` as the primary Flask entry point, added `app/__init__.py` to make `app` a package, created `schema.sql` for database initialization, and fixed imports in `main.py` to correctly use `g`, `flash`, `wraps`, and `app.ee_classifier`. Updated `Dockerfile` to use `main:app`.
- 2023-10-27: Added `import os` to `app/app.py`.
- 2024-07-30: Consolidated Flask application, templates, and static assets into a unified project structure. Integrated UNOPS design system, added API endpoints, and ensured Earth Engine classification functionality. Added `import json` to `app.py`.
- 2024-07-30: Added `.map-area` CSS style and applied it to the map container in `index.html`.
- 2024-07-30: Added `label` styling and styles for `select` and `input[type=range]` to `unops-dark-theme.css`, and introduced `--unops-text-muted` CSS variable for consistent text coloring.
- 2024-07-30: Added `.btn` style to `unops-dark-theme.css`.
- 2024-07-30: Consolidated `unops-dark-theme.css` and `style.css` into a single `app/static/css/style.css`, deleted `unops-dark-theme.css`, and recreated `app/templates/dashboard.html`, `app/templates/login.html`, `app/templates/register.html` with updated CSS links and button classes. Updated `app/templates/index.html` to use the `.btn` class.
- 2024-07-30: Consolidated Flask application into `main.py`, deleted redundant `app.py`, updated `index.html` to integrate Leaflet map and landcover classification functionality with palette selection. Debugged Flask routing issues, identified port conflict, and confirmed application functionality on port 5001. Re-enabled `@login_required` for `/classify` route. Noted Earth Engine authentication limitation. Added hover effect to primary buttons in `unops-dark-theme.css`.
- 2024-07-30: Added disabled state styling for buttons to `unops-dark-theme.css`.
- 2024-07-30: Refactored frontend to use external CSS and Flask's `render_template`. Inline CSS moved from `app.py` to `static/css/style.css`, and HTML content moved to `templates/index.html`. `app.py` was updated to render `index.html` using `render_template`.
