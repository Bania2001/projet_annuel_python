import json
import sys
import koceimba as Cube
import boto3


# Initialiser le client S3
session = boto3.Session(region_name="eu-west-1")
s3 = session.client("s3")


# Télécharger le fichier JSON depuis S3
def download_json_from_s3(bucket_name, key):
    response = s3.get_object(Bucket=bucket_name, Key=key)
    data = response["Body"].read().decode("utf-8")
    return json.loads(data)


# Convertir les couleurs en cubestring compatible avec Kociemba
def input_colors_to_cubestring(input_colors):
    color_map = {
        "w": "U",  # White -> Up
        "y": "D",  # Yellow -> Down
        "g": "F",  # Green -> Front
        "b": "B",  # Blue -> Back
        "o": "R",  # Orange -> Right
        "r": "L",  # Red -> Left
    }

    cubestring = ""

    for face_colors in input_colors:
        for row in face_colors:
            for color in row:
                if color is None:
                    continue
                cubestring += color_map[color]

    return cubestring


# Résoudre le cube
def solve_rubiks_cube(bucket_name, key, output_bucket):
    input_colors = download_json_from_s3(bucket_name, key)
    cubestring = input_colors_to_cubestring(input_colors)

    print("Cubestring:", cubestring)
    try:
        solution = Cube.solve(cubestring)
        if solution:
            print("Solution:", solution)
            # Écrire les résultats directement dans S3
            resultats_json = json.dumps({"solution": solution}, indent=2)
            output_key = "bravo.json"
            s3.put_object(Bucket=output_bucket, Key=output_key, Body=resultats_json)
            print(
                f"Résultats téléchargés dans le bucket S3 : {output_bucket}/{output_key}"
            )
            return solution
    except Exception as e:
        print("Error solving the cube:", e)
        return None


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python solve_rubiks_cube.py <bucket> <key> <output_bucket>")
        sys.exit(1)
    bucket_name = sys.argv[1]
    key = sys.argv[2]
    output_bucket = sys.argv[3]
    solve_rubiks_cube(bucket_name, key, output_bucket)
