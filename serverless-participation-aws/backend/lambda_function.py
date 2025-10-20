import json
import boto3
import urllib.parse
import base64
import re
from datetime import datetime

# Initialize AWS service clients
textract_client = boto3.client('textract')
rekognition_client = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

# Configuration
DDB_TABLE = 'cicc-participation-table'
REFERENCE_BUCKET = 'participation-record'
UPLOAD_BUCKET = 'participation-record'  # Bucket for user-uploaded images
REFERENCE_IMAGES = [
    'p02_photos/faces1_Feb17.jpg',
    'p02_photos/faces2_Feb17.jpg',
    'p02_photos/faces3_Feb17.jpg'
]
# New: Configuration for the reference text image (for Textract)
TEXT_REFERENCE_IMAGE = 'p02_photos/names1_Feb17.jpg'

similarity_threshold = 80.0  # For face comparisons

def lambda_handler(source, context):
    # print(event)
    try:
        # Parse the event body
        if 'body' in source:
            request = json.loads(source['body'])
        else:
            request = source
        
        # Extract fields
        files = request.get('files', [])
        student_name = request.get('name')
        student_email = request.get('email')
        class_date = request.get('classDate')
        
        if not (files and student_name and student_email and class_date):
            missing = [k for k in ['files', 'name', 'email', 'classDate'] if not request.get(k)]
            raise KeyError(f"Missing parameters: {', '.join(missing)}")
    except Exception as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Invalid input: {str(e)}'})
        }
    
    # --- 1. Upload files to S3 and collect URLs ---
    source_urls = []
    uploaded_image_key = None  # to store key of the first uploaded image
    for idx, file_data in enumerate(files):
        file_name = file_data['fileName']
        file_content = file_data['fileContent']
        # Extract base64 data
        if ',' in file_content:
            file_content = file_content.split(',')[1]
        file_bytes = base64.b64decode(file_content)
        s3_key = f"uploads/{student_email}/{file_name}"
        s3_client.put_object(
            Bucket=UPLOAD_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            ContentType='image/jpeg'  # Adjust based on file type if needed
        )
        s3_url = f"https://{UPLOAD_BUCKET}.s3.amazonaws.com/{s3_key}"
        source_urls.append(s3_url)
        if idx == 0:
            uploaded_image_key = s3_key  # Use the first uploaded file for processing
    
    if not uploaded_image_key:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'No uploaded image found.'})
        }
    
    # --- 2. Face Detection & Comparison ---
    # Detect faces in the uploaded image using detect_faces
    try:
        uploaded_faces_resp = rekognition_client.detect_faces(
            Image={'S3Object': {'Bucket': UPLOAD_BUCKET, 'Name': uploaded_image_key}},
            Attributes=['DEFAULT']
        )
        uploaded_faces = uploaded_faces_resp.get('FaceDetails', [])
    except Exception as e:
        uploaded_faces = []
        print("Error detecting faces in uploaded image:", str(e))
    
    faceParticipation = False
    all_details = []
    
    # For each reference image, detect faces and compare
    for ref_key in REFERENCE_IMAGES:
        try:
            # Detect faces in the reference image
            ref_faces_resp = rekognition_client.detect_faces(
                Image={'S3Object': {'Bucket': REFERENCE_BUCKET, 'Name': ref_key}},
                Attributes=['DEFAULT']
            )
            ref_faces = ref_faces_resp.get('FaceDetails', [])
            ref_match_found = False
            match_details = []
            
            # For each face in the uploaded image, compare with the reference image using compare_faces
            for uploaded_face in uploaded_faces:
                compare_response = rekognition_client.compare_faces(
                    SourceImage={'S3Object': {'Bucket': UPLOAD_BUCKET, 'Name': uploaded_image_key}},
                    TargetImage={'S3Object': {'Bucket': REFERENCE_BUCKET, 'Name': ref_key}},
                    SimilarityThreshold=similarity_threshold
                )
                face_matches = compare_response.get('FaceMatches', [])
                for match in face_matches:
                    similarity = match.get('Similarity', 0)
                    if similarity >= similarity_threshold:
                        ref_match_found = True
                        match_details.append({'Similarity': similarity})
                        break
                if ref_match_found:
                    break
                    
            if ref_match_found:
                faceParticipation = True
            all_details.append({
                'referenceImage': f"https://{REFERENCE_BUCKET}.s3.amazonaws.com/{ref_key}",
                'faceMatchFound': ref_match_found,
                'matchDetails': match_details,
                'uploadedFacesCount': len(uploaded_faces),
                'referenceFacesCount': len(ref_faces)
            })
        except Exception as e:
            print(f"Error comparing with reference image {ref_key}: {str(e)}")
            all_details.append({
                'referenceImage': f"https://{REFERENCE_BUCKET}.s3.amazonaws.com/{ref_key}",
                'error': str(e)
            })
    
    # --- 3. Name Extraction using Textract ---
    nameParticipation = False
    try:
        # Use the reference text image (stored in S3) for text extraction
        textract_response = textract_client.detect_document_text(
            Document={'S3Object': {'Bucket': REFERENCE_BUCKET, 'Name': TEXT_REFERENCE_IMAGE}}
        )

         # Get all text lines in lowercase for consistent comparison
        extracted_lines = [
            block['Text'].strip().lower()
            for block in textract_response.get('Blocks', [])
            if block.get('BlockType') == 'LINE'
        ]


        # Prepare student name for matching (lowercase and clean whitespace)
        student_name_clean = ' '.join(student_name.lower().split())
        # print(f"Student name for matching: {student_name_clean}")

        for line in extracted_lines:
            # Clean line: remove special characters and extra spaces
            cleaned_line = ' '.join(line.replace('(', ' ').replace(')', ' ')
                                  .replace(',', ' ').split()).lower()
            print(f"Cleaned line: {cleaned_line}")
            
            if student_name_clean in cleaned_line:
                nameParticipation = True
                print(f"Name match found in line: {line}")
                break
        # extracted_text = " ".join(
        #     item.get('Text', '')
        #     for item in textract_response.get('Blocks', [])
        #     if item.get('BlockType') == 'LINE'
        # )
        # This will match multi-word names like "Shuai Zhang", "IMAM UDDIN MOHAMMED", etc.
        # pattern = r'\b([a-z]+(?: [a-z]+)+)\b'
        # # Find all matches based on the pattern
        # potential_names = re.findall(pattern, extracted_text)
        # print("Potential names:", potential_names)
        # # Filter out common non-name terms (you can add more terms to exclude if necessary)
        # excluded_terms = ['host', 'me', 'find', 'invite', 'mute', 'all', 'participants', 'x', 'pa', 'sr']
        # cleaned_names = [name.title() for name in potential_names if name not in excluded_terms]
        # print("Extracted text:", extracted_text)
        # Compare extracted text with student's name (case-insensitive)
        # if student_name.lower() in extracted_text.lower():
        #     nameParticipation = True
    except Exception as e:
        print("Error in Textract processing:", str(e))
    
    # --- 4. Determine Overall Participation ---
    # Student is considered to have participated if either face participation or name participation is true.
    participation = faceParticipation or nameParticipation
    
    # --- 5. Write the participation record to DynamoDB ---
    try:
        table = dynamodb.Table(DDB_TABLE)
        table.put_item(
            Item={
                'email': student_email,
                'classDate': class_date,
                'name': student_name,
                'participation': participation,
            }
        )
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Error writing to DynamoDB',
                'details': str(e)
            })
        }
    
    # --- 6. Return the final result ---
    result = {
        'name': student_name,
        'email': student_email,
        'classDate': class_date,
        'participation': participation,
        'details': {  # Add details about participation
        'faceParticipation': faceParticipation,
        'nameParticipation': nameParticipation
        }
    }
    print(result)
    
    return {
        'statusCode': 200,
        'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
        'body': json.dumps(result)
    }
