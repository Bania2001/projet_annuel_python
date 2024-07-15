import sys
import os
import json
import zipfile
import tempfile
import cv2
import numpy as np
import boto3

# Assurez-vous que boto3 utilise la bonne région
session = boto3.Session(region_name="eu-west-1")
s3 = session.client("s3")
# Définir les plages de couleurs en HSV a ajuster o et r
plages_couleurs = {
    "r": [((0, 100, 100), (10, 255, 255)), ((160, 100, 100), (180, 255, 255))],
    "o": ((10, 100, 200), (20, 255, 255)),
    "y": ((20, 150, 100), (30, 255, 255)),
    "g": ((35, 100, 100), (85, 255, 255)),
    "b": ((85, 100, 100), (125, 255, 255)),
    "w": [((0, 0, 200), (180, 30, 255)), ((0, 0, 180), (180, 30, 255))],
}


def detecter_couleur_dominante(cellule):
    hsv_cellule = cv2.cvtColor(cellule, cv2.COLOR_BGR2HSV)
    couleur_max = None
    max_count = 0
    for couleur, plages in plages_couleurs.items():
        if isinstance(plages, list):
            count = 0
            for lower, upper in plages:
                masque = cv2.inRange(hsv_cellule, lower, upper)
                count += cv2.countNonZero(masque)
        else:
            lower, upper = plages
            masque = cv2.inRange(hsv_cellule, lower, upper)
            count = cv2.countNonZero(masque)
        if count > max_count:
            max_count = count
            couleur_max = couleur
    return couleur_max


def traiter_zip_depuis_s3(bucket, key, output_bucket):
    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            chemin_zip = os.path.join(tmpdirname, "file.zip")
            s3.download_file(bucket, key, chemin_zip)
            with zipfile.ZipFile(chemin_zip, "r") as zip_ref:
                zip_ref.extractall(tmpdirname)

            # Le zip arrive désordonnée pour cela  on définit l'ordre comme ça nous allons pas avoir  problems avec l'algo de résolution
            def sort_key(filename):
                order = ["W", "O", "G", "Y", "R", "B"]
                for i, prefix in enumerate(order):
                    if filename.upper().startswith(prefix):
                        return i
                return len(order)  # cas spec

            files = sorted(
                [
                    f
                    for f in os.listdir(tmpdirname)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ],
                key=sort_key,
            )
            toutes_couleurs_faces = []
            for nom_fichier in files:
                chemin_img = os.path.join(tmpdirname, nom_fichier)
                img = cv2.imread(chemin_img)
                if img is None:
                    continue
                print(f"Traitement de l'image: {nom_fichier}")
                # image en gris pour éliminer les informations des couleurs
                gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                # le  flou pour réduire le bruit
                blurred_image = cv2.GaussianBlur(gray_image, (5, 5), 0)
                # la détection des contours de Canny
                edges = cv2.Canny(blurred_image, 30, 170)
                # 2 itération pour bien dilater les bors et ne pas avoir de vide
                noyau = np.ones((5, 5), np.uint8)
                edges_dilated = cv2.dilate(edges, noyau, iterations=2)
                # Trouver les contours
                contours, hierarchy = cv2.findContours(
                    edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                # Trouver le contour avec la plus grande aire
                max_area = 0
                max_contour = None
                for i, contour in enumerate(contours):
                    area = cv2.contourArea(contour)
                    if area > max_area:
                        max_area = area
                        max_contour = contour
                if max_contour is not None:
                    # Trouver le rectangle englobant le plus grand contour
                    x, y, w, h = cv2.boundingRect(max_contour)
                    rect_contour = np.array(
                        [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
                    )
                    # Découper l'image pour n'avoir que la face du Rubik's cube
                    img_decoupee = img[y : y + h, x : x + w]
                    # Diviser en une grille 3x3
                    largeur_cellule = w // 3
                    hauteur_cellule = h // 3
                    grille_couleurs = [["" for _ in range(3)] for _ in range(3)]
                    for i in range(3):
                        for j in range(3):
                            cellule = img_decoupee[
                                i * hauteur_cellule : (i + 1) * hauteur_cellule,
                                j * largeur_cellule : (j + 1) * largeur_cellule,
                            ]
                            couleur = detecter_couleur_dominante(cellule)
                            grille_couleurs[i][j] = couleur
                    toutes_couleurs_faces.append(grille_couleurs)
                else:
                    print(f"Aucun contour détecté dans l'image {nom_fichier}.")
            # Écrire les résultats directement dans S3
            resultats_json = json.dumps(toutes_couleurs_faces, indent=2)
            output_key = "resultats_photos_bania.json"
            s3.put_object(Bucket=output_bucket, Key=output_key, Body=resultats_json)
            print(
                f"Résultats téléchargés dans le bucket S3 : {output_bucket}/{output_key}"
            )
    except Exception as e:
        print(f"Erreur rencontrée: {str(e)}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python detectionColor.py <bucket> <key> <output_bucket>")
        sys.exit(1)
    nom_du_bucket = sys.argv[1]
    cle_objet = sys.argv[2]
    output_bucket = sys.argv[3]
    traiter_zip_depuis_s3(nom_du_bucket, cle_objet, output_bucket)
