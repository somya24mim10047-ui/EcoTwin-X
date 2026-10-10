# EcoTwin-X: HeatStop & CoolPath

**Problem.** Delivery riders, street vendors and children in Indian cities spend hours
outside in heat and traffic fumes, and the shortest route is often the worst for them.
City teams also cannot tell which shade, tree or cooling-stop investment helps most.

**What it does.**
- **CoolPath** finds a route with more shade and cleaner air, per worker type and hour,
  and shows the exposure cut against the extra minutes.
- **HeatStop Planner** ranks real places (parks, schools, hospitals) for cooling stops.
- **Intervention Optimizer** finds the best mix of stops, trees and green corridors for a budget.
- **AI Planner** is a Strands agent: ask in plain English, it calls the tools above.

**Study area:** central Bhopal, India (OpenStreetMap roads and buildings, sun-angle shadows).

**AWS.** Built with the AWS open-source **Strands Agents SDK** (`ecotwin/agent.py`);
runs on AWS via Docker (see `DEPLOY_AWS.md`).

## Run locally
```
pip install -r requirements.txt
streamlit run app.py
```

## Honest limits
- Intervention costs and effects (`data/interventions.csv`) are assumptions, so
  results are planning simulations, not measurements.
- The pollution layer is a road-class proxy, not sensor data.
- "Validation" checks internal consistency, not agreement with field measurements.
