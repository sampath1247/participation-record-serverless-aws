# participation-record-serverless-aws
Attendance verification on AWS: upload photo → match face/name with Rekognition/Textract → store result in DynamoDB; API Gateway + Lambda + S3; Amplify frontend.
# Serverless Participation Verification on AWS (Face + Name)

Course: Applications Database Systems  
Author: Sampath Valluri (sampathvalluri18@gmail.com)

A serverless web app that verifies student participation using:
- Face matching with Amazon Rekognition against a reference classroom photo in S3
- Name extraction with Amazon Textract against a reference names image in S3
- Records participation to DynamoDB when either face or name matches

## Architecture

Flow:
1) Frontend (Amplify-hosted) collects name, email, date, and a photo and calls an API Gateway endpoint (POST, CORS enabled).
2) Lambda receives payload, uploads the user photo to S3, runs Rekognition (face compare) and Textract (name match).
3) If either match is true, Lambda writes a record to DynamoDB: { name, email, classDate, participation }.
4) Frontend displays the result.

See docs/diagram.mmd for a diagram.

## Tech Stack

- AWS: Lambda, API Gateway, S3, DynamoDB, Rekognition, Textract, Amplify, IAM
- Language: Python (Lambda), HTML/CSS/JS (frontend)

## Repository Layout

- backend/lambda_function.py — Lambda code
- frontend/index.html — Frontend UI
- docs/ — Report, architecture diagram, IAM policy sample, API payload example, cleanup checklist
- .github/workflows/ci.yml — CI lint/smoke check for Python

## Setup and Configuration

Environment configuration expected by Lambda (set as environment variables in AWS Lambda):
- S3_BUCKET_UPLOADS: S3 bucket for user-uploaded images
- S3_BUCKET_REFERENCES: S3 bucket for reference images
- REFERENCE_FACE_KEY: Object key for the classroom faces image (e.g., faces.jpg)
- REFERENCE_NAMES_KEY: Object key for the names image (e.g., names.jpg)
- DDB_TABLE_NAME: DynamoDB table (e.g., cicc-participation-table)
- SIMILARITY_THRESHOLD: e.g., "90" (string)

IAM (least privilege):
- s3:GetObject, s3:PutObject, s3:ListBucket on the specific buckets
- rekognition:DetectFaces, rekognition:CompareFaces
- textract:DetectDocumentText (and/or AnalyzeDocument if used)
- dynamodb:PutItem on the specific table

See docs/iam-policy.json for a template.

## API

Endpoint: POST https://<api-id>.execute-api.<region>.amazonaws.com/<stage>/participation

Request payload (example in docs/api-request.json):
```json
{
  "name": "Jane Doe",
  "email": "jane.doe@example.com",
  "classDate": "2025-03-09",
  "imageBase64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."
}
```

Response example:
```json
{
  "name": "Jane Doe",
  "email": "jane.doe@example.com",
  "classDate": "2025-03-09",
  "faceParticipation": true,
  "nameParticipation": false,
  "participation": true
}
```

## Local Development

Install tools:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Lint check (CI mirrors this):
```bash
flake8
```

Note: Lambda uses AWS-managed boto3 at runtime. requirements.txt is for local linting/testing.

## Deployment (High-level)

1) Create S3 buckets:
   - uploads bucket (for user images)
   - references bucket (faces.jpg, names.jpg)
2) Create DynamoDB table (e.g., cicc-participation-table) with partition/sort keys that match your code (e.g., email + classDate).
3) Create IAM role/policy for Lambda (see docs/iam-policy.json).
4) Create Lambda function, set environment variables, attach IAM role.
5) Create API Gateway (REST), POST /participation, Lambda proxy, enable CORS; deploy a stage.
6) Deploy frontend to Amplify; set API endpoint in frontend code.

## Testing

- Unit tests: Invoke Lambda with sample payloads (API Gateway proxy style). Validate Rekognition/Textract branches and DynamoDB writes.
- End-to-end: From Amplify site, submit a photo and name → verify record in DynamoDB.

## Cost and Cleanup

- Fits within AWS Free Tier for a student project (Lambda, API Gateway, S3, DynamoDB, IAM; Rekognition/Textract within monthly limits for small workloads).
- After demo:
  - Delete/empty S3 buckets, delete DynamoDB table, remove API/Lambda, and delete custom IAM roles/policies.
  - Set AWS Budgets/alerts to avoid unexpected charges.

See docs/cleanup-checklist.md.

## Notes and Lessons

- Designed a robust “either face OR name” participation decision to improve recall of valid participants.
- Emphasis on least-privilege IAM and environment-driven configuration for portability.

## License

MIT — see LICENSE.
