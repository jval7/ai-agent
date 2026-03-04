import google.cloud.firestore as google_cloud_firestore


def build_client(project_id: str, database_id: str) -> google_cloud_firestore.Client:
    return google_cloud_firestore.Client(project=project_id, database=database_id)
