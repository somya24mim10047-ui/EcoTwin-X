# Deploy EcoTwin-X on AWS (Lightsail containers, about 15 minutes)

Free-tier credits cover this. Streamlit needs WebSockets, so use Lightsail or EC2
rather than Lambda.

## Option A: Lightsail container service (easiest)
1. Install Docker and the AWS CLI + Lightsail plugin, then `aws configure`.
2. Build: `docker build -t ecotwin-x .`
3. Test locally: `docker run -p 8501:8501 ecotwin-x` -> http://localhost:8501
4. Create the service (Lightsail console -> Containers -> Create container service,
   Nano or Micro power, scale 1).
5. Push: `aws lightsail push-container-image --service-name ecotwin-x --label app --image ecotwin-x`
6. In the console, create a deployment with that image, port 8501, HTTP, and mark
   the container as the public endpoint. Health check path: `/_stcore/health`.
7. Open the public URL shown on the service page. That is your submission URL.

## Option B: EC2
Launch Ubuntu t3.small, open port 8501 in the security group, install Docker,
copy the project, run the docker commands from steps 2-3 with `-d --restart always`.

## Turn on the Strands agent
- Amazon Bedrock: enable a model in the Bedrock console, give the service an IAM
  role (or env vars AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION), and
  set BEDROCK_MODEL_ID to a model you have access to.
- No AWS account: run Ollama locally and set `ECOTWIN_MODEL=ollama`,
  `OLLAMA_MODEL=llama3.1`.
- With neither, the AI Planner page shows "Offline mode" (same tools, rule-based).

## Optional: data in S3
Upload `data/` to a bucket and download it at container start with boto3.
