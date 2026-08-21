# FiremeX — fully-local Home Assistant add-on.
#
# Detection runs here, on the Home Assistant machine. Frames come from Home
# Assistant's own camera entities and hazards are published straight back to
# Home Assistant. There is no FiremeX cloud in this deployment.
#
# Built from the REPOSITORY ROOT, because it reuses two things rather than
# reimplementing them: the shared detection package (backend/app/detection) and
# the site agent's pipeline and model-fetching code (edge/). Keeping one copy of
# the detection logic is the point — a second copy would drift, and in this
# product that means a site running a detector we thought we had replaced.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Same dependency set as the site agent — deliberately, so the two cannot drift
# onto different torch/ultralytics versions and detect differently.
COPY edge/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY edge/ ./
COPY backend/app/ ./app/
COPY ha_agent/ ./ha_agent/

# /data is the add-on's persistent volume, so weights survive add-on updates.
ENV MODEL_PATH=/data/fire_model.pt \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "ha_agent.main"]
