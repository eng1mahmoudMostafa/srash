# Render example build steps (also used by render.yaml above)
build:
  - cd backend && pip install -r requirements.txt
  - cd frontend && npm ci && npm run build
  - cd backend && python manage.py collectstatic --noinput