from fastapi import APIRouter

router = APIRouter()

# This file is intentionally left blank after refactoring.
# All routes have been moved to more specific files:
# - manage.py: for the root redirect and the HTML management page.
# - tasks.py: for background task management (e.g., tag_all_media).
# - webhook.py: for handling the Emby webhook.
