"""
Projet 9 - Mission 2 : agregation des fichiers sources.

A EXECUTER EN LOCAL (le CSV des charts fait ~1,5 Go).
Lecture par chunks : la memoire utilisee reste de l'ordre de 300 Mo.

Produit 4 fichiers legers (~1 a 3 Mo au total) a transmettre pour la suite :
  1. serie_global_par_genre.csv     - date x genre : nb de morceaux distincts dans le Top 200
  2. serie_global_total.csv         - date : nb de morceaux distincts, tous genres confondus
  3. diagnostic_collecte.csv        - date : nb de lignes et de marches, TOUS marches confondus
  4. sorties_mensuelles_par_genre.csv - mois x genre : nb de sorties officielles

Usage : adapter les 3 constantes ci-dessous, puis executer le fichier.
"""

import pandas as pd

# ---------------------------------------------------------------------------
# PARAMETRES
# ---------------------------------------------------------------------------
CHEMIN_CHARTS  = "chart_tracks_genre_2017_2020+(1).csv"
CHEMIN_RELEASE = "release_dates_genre_2017_2020.csv"

# Marches conserves dans le detail par genre. "Global" suffit pour la mission ;
# en ajouter d'autres multiplie la taille des sorties (~300 Ko par marche).
MARCHES = ["Global"]

TAILLE_CHUNK = 1_000_000


# ---------------------------------------------------------------------------
# 1. LECTURE PAR CHUNKS DU FICHIER DES CLASSEMENTS
# ---------------------------------------------------------------------------
# On ne charge que 4 colonnes sur 8 : `track`, `title`, `artist` et `position`
# ne servent pas au comptage et representent l'essentiel du poids du fichier.
COLONNES_UTILES = ["country", "date", "uri", "genre"]

morceaux = []        # lignes des marches retenus, conservees en entier
diag_lignes = []     # comptage par date, tous marches confondus
n_lignes_total = 0

lecteur = pd.read_csv(
    CHEMIN_CHARTS,
    usecols=COLONNES_UTILES,
    dtype={"country": "str", "date": "str", "uri": "str", "genre": "str"},
    chunksize=TAILLE_CHUNK,
)

for i, chunk in enumerate(lecteur, start=1):
    n_lignes_total += len(chunk)

    # Diagnostic de collecte : volumetrie par date sur l'ensemble des marches.
    # Sert a distinguer un vrai zero d'un trou de collecte (etape 4 du brief).
    diag_lignes.append(
        chunk.groupby("date").agg(
            n_lignes=("uri", "size"),
            n_marches=("country", "nunique"),
        )
    )

    # Detail par genre : uniquement sur les marches retenus
    sous_ensemble = chunk[chunk["country"].isin(MARCHES)]
    if len(sous_ensemble):
        morceaux.append(sous_ensemble)

    print(f"  chunk {i:>2} traite - {n_lignes_total:>10,} lignes lues", flush=True)

df = pd.concat(morceaux, ignore_index=True)
print(f"\nLignes totales lues            : {n_lignes_total:,}")
print(f"Lignes conservees ({', '.join(MARCHES)}) : {len(df):,}")


# ---------------------------------------------------------------------------
# 2. CONVERSION DES DATES + VERIFICATION DU FORMAT
# ---------------------------------------------------------------------------
# Le fichier affiche 05/11/2020. Deux lectures possibles : 5 novembre (JJ/MM)
# ou 11 mai (MM/JJ). On tranche sur preuve, pas sur hypothese : si une valeur
# du premier champ depasse 12, ce champ ne peut etre qu'un jour.
premier_champ = df["date"].str.split("/").str[0].astype(int)
second_champ = df["date"].str.split("/").str[1].astype(int)
print(f"\nMax du 1er champ de date : {premier_champ.max()}  (>12 => JJ/MM/AAAA)")
print(f"Max du 2e champ de date  : {second_champ.max()}")

df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")

n_dates_ko = df["date"].isna().sum()
print(f"Dates non converties     : {n_dates_ko:,}")
print(f"Periode couverte         : {df['date'].min():%Y-%m-%d} -> {df['date'].max():%Y-%m-%d}")
print(f"Jours calendaires distincts : {df['date'].nunique():,}")

# Normalisation des genres (casse et espaces parasites)
df["genre"] = df["genre"].str.strip().str.lower()
print(f"\nGenres presents ({df['genre'].nunique()}) :")
print(df["genre"].value_counts().to_string())


# ---------------------------------------------------------------------------
# 3. SERIES QUOTIDIENNES
# ---------------------------------------------------------------------------
# On compte des morceaux DISTINCTS (nunique sur uri) et non des lignes :
# un meme morceau peut apparaitre plusieurs fois le meme jour sur un marche
# s'il est rattache a plusieurs genres, ou en cas de doublon de collecte.

# 3a. Serie par genre
serie_genre = (
    df.groupby(["country", "date", "genre"])
      .agg(n_morceaux=("uri", "nunique"), n_lignes=("uri", "size"))
      .reset_index()
      .sort_values(["country", "genre", "date"])
)

# 3b. Serie totale, tous genres confondus (reference du diagnostic des zeros)
serie_total = (
    df.groupby(["country", "date"])
      .agg(n_morceaux_total=("uri", "nunique"), n_lignes_total=("uri", "size"))
      .reset_index()
      .sort_values(["country", "date"])
)

# 3c. Diagnostic de collecte, tous marches confondus
diag = (
    pd.concat(diag_lignes)
      .groupby(level=0)
      .sum()
      .reset_index()
)
diag["date"] = pd.to_datetime(diag["date"], format="%d/%m/%Y", errors="coerce")
diag = diag.sort_values("date")

print(f"\nSerie par genre  : {len(serie_genre):,} lignes")
print(f"Serie totale     : {len(serie_total):,} lignes")
print(f"Diagnostic       : {len(diag):,} dates")

ecart = serie_total["n_lignes_total"] - serie_total["n_morceaux_total"]
print(f"Jours ou lignes > morceaux distincts : {(ecart > 0).sum():,} "
      f"(doublons uri ou morceaux multi-genres)")


# ---------------------------------------------------------------------------
# 4. CADENCE MENSUELLE DES SORTIES (2e fichier, petit)
# ---------------------------------------------------------------------------
rel = pd.read_csv(CHEMIN_RELEASE, usecols=["Uri", "Release_date", "Genre_new"])
rel["Release_date"] = pd.to_datetime(rel["Release_date"], errors="coerce")
rel["Genre_new"] = rel["Genre_new"].str.strip().str.lower()

print(f"\nFichier des sorties : {len(rel):,} lignes")
print(f"  dates non converties : {rel['Release_date'].isna().sum():,}")
print(f"  Uri distincts        : {rel['Uri'].nunique():,}")
print(f"  periode              : {rel['Release_date'].min():%Y-%m-%d} -> "
      f"{rel['Release_date'].max():%Y-%m-%d}")

rel = rel.dropna(subset=["Release_date"])
sorties = (
    rel.assign(mois=rel["Release_date"].dt.to_period("M").dt.to_timestamp())
       .groupby(["mois", "Genre_new"])
       .agg(n_sorties=("Uri", "nunique"))
       .reset_index()
       .rename(columns={"Genre_new": "genre"})
       .sort_values(["genre", "mois"])
)
print(f"  serie mensuelle      : {len(sorties):,} lignes")


# ---------------------------------------------------------------------------
# 5. EXPORT
# ---------------------------------------------------------------------------
serie_genre.to_csv("serie_global_par_genre.csv", index=False)
serie_total.to_csv("serie_global_total.csv", index=False)
diag.to_csv("diagnostic_collecte.csv", index=False)
sorties.to_csv("sorties_mensuelles_par_genre.csv", index=False)

print("\n--- Fichiers ecrits ---")
for f in ["serie_global_par_genre.csv", "serie_global_total.csv",
          "diagnostic_collecte.csv", "sorties_mensuelles_par_genre.csv"]:
    print(f"  {f}")
