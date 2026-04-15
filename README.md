# landcover-classifier

Created with OverGravity.

This project implements a landcover classifier using Earth Engine and a pre-trained Random Forest model, with an improved training process for better accuracy.

The application is built with Flask, using a single `app.py` file for the backend logic and API endpoints. The frontend is structured with `templates/index.html` for the main page and `static/css/style.css` for styling, adhering to the UNOPS COMPASS design system.

**Note on Earth Engine Authentication:** This application relies on Google Earth Engine. For the classifier to function, Earth Engine must be properly authenticated in the environment (e.g., via `earthengine authenticate` with the correct project ID `unops-gpo-psc-prtnshp-dev`). Without proper authentication, the land cover classification functionality will not work.
