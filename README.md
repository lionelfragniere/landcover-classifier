# landcover-classifier

Created with OverGravity.

This project implements a landcover classifier using Earth Engine and a pre-trained Random Forest model, with an improved training process for better accuracy.

The application is built with Flask, using a single `app.py` file for the backend logic and API endpoints. The frontend is structured with `templates/index.html` for the main page and `static/css/style.css` for styling, adhering to the UNOPS COMPASS design system.

**Deployment Status:**
- The application has been deployed to Google Cloud Run at: `https://landcover-classifier-700845207803.us-central1.run.app/`
- **Note:** The deployment was intended for `europe-west1` but was deployed to `us-central1` due to a limitation in the deployment tool which does not allow specifying the region.

**UNOPS Design System Compliance & Known Issues:**
- The application now defaults to a light theme, with Inter font for body text and Inter Tight for headings.
- Primary, supporting, and semantic colors are applied.
- Buttons have 8px border-radius and primary background.
- Cards have 12px border-radius, white background, and specified shadow.
- The UNOPS logo (`static/unops-logo.png`) is now correctly referenced and a placeholder is in place.
- The Earth Engine project ID is now an environment variable (`EE_PROJECT_ID`).

**Note on Earth Engine Authentication:** This application relies on Google Earth Engine. For the classifier to function, Earth Engine must be properly authenticated in the environment (e.g., via `earthengine authenticate` with the correct project ID `unops-gpo-psc-prtnshp-dev`). Without proper authentication, the land cover classification functionality will not work.
