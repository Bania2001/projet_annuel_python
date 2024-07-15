import json
import subprocess
import boto3

# Configuration
SQS_QUEUE_URL = (
    "https://sqs.eu-west-1.amazonaws.com/128320606219/rubikscube-solution-queue"
)
FINAL_BUCKET = "rubikscube-final"
REQUIRED_KEY = "user_input_colors.json"
# Initialiser le client  SQS
sqs = boto3.client("sqs")


def traiter_message(corps_du_message):
    try:
        info_s3 = json.loads(corps_du_message)
        enregistrements = info_s3.get("Records", [])
        for enregistrement in enregistrements:
            s3 = enregistrement.get("s3", {})
            bucket = s3.get("bucket", {}).get("name")
            key = s3.get("object", {}).get("key")

            if bucket == FINAL_BUCKET and key == REQUIRED_KEY:
                # Exécuter le script de résolution du Rubik's cube
                print(f"Résolution du fichier depuis le bucket: {bucket}, clé: {key}")
                subprocess.run(
                    [
                        "/home/ubuntu/projet_annuel/myenv/bin/python3",
                        "/home/ubuntu/projet_annuel/solve_rubiks_cube.py",
                        bucket,
                        key,
                        FINAL_BUCKET,
                    ],
                    check=True,
                )

    except Exception as e:
        print(f"Erreur lors du traitement du message : {str(e)}")


def main():
    while True:
        response = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL, MaxNumberOfMessages=1, WaitTimeSeconds=20
        )

        messages = response.get("Messages", [])
        if messages:
            for message in messages:
                corps_du_message = message.get("Body")
                traiter_message(corps_du_message)
                receipt_handle = message.get("ReceiptHandle")

                # Supprimer le message de la file d'attente une fois traité
                sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
        else:
            print("Aucun message reçu. Attente de nouveaux messages...")


if __name__ == "__main__":
    main()
