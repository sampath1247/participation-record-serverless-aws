# Lambda configuration

Environment variables (set in Lambda console):
- UPLOAD_BUCKET
- REFERENCE_BUCKET
- REFERENCE_FACES_KEY
- REFERENCE_NAMES_KEY
- DDB_TABLE
- SIMILARITY_THRESHOLD
- REGION

Expected event format:
```json
{
  "name": "Alice Smith",
  "email": "alice@example.com",
  "classDate": "2025-03-10",
  "userImageBase64": "<base64-encoded JPEG/PNG>"
}
```

Outputs:
- Writes the uploaded image to `UPLOAD_BUCKET`
- Uses Rekognition CompareFaces against `REFERENCE_BUCKET/REFERENCE_FACES_KEY` (top match >= threshold)
- Uses Textract DetectDocumentText on `REFERENCE_BUCKET/REFERENCE_NAMES_KEY` to look for the provided name
- Writes item to DynamoDB `DDB_TABLE`:
  - { email, classDate, name, faceParticipation: bool, nameParticipation: bool, participated: bool, ts }

Return value:
```json
{
  "statusCode": 200,
  "body": "{\"participated\":true,...}",
  "headers": { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
}
```