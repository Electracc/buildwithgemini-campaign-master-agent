import os
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-01-141f75f249db"

print("--- Testing gRPC Firestore ---")
try:
    db = firestore.Client(project=PROJECT_ID, database="(default)")
    doc = db.collection("monsters").document("test").get()
    print("gRPC Success! doc exists:", doc.exists)
except Exception as e:
    print("gRPC error:", e)

print("\n--- Testing REST Firestore ---")
try:
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.services.firestore.transports.rest import FirestoreRestTransport
    
    client = Client(project=PROJECT_ID, database="(default)", transport=FirestoreRestTransport)
    doc = client.collection("monsters").document("test").get()
    print("REST Success! doc exists:", doc.exists)
except Exception as e:
    print("REST error:", e)
