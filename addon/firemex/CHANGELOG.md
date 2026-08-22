# Changelog

## 0.2.0

- First release available as a Home Assistant add-on.
- The agent image now reads its configuration from the add-on's
  `/data/options.json` as well as from environment variables, so the same
  image serves both the add-on and the Docker Compose install.
- Model weights are stored in `/data`, so they survive add-on updates.

## 0.1.0

- Initial edge agent, installed with Docker Compose.
