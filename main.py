from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import random
from typing import Optional
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

# --- CONFIGURATION NEON ---
DATABASE_URL = os.environ.get("DATABASE_URL")

# Création du moteur de connexion
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODÈLE DE LA TABLE (SQLAlchemy) ---
class UtilisateurDB(Base):
    __tablename__ = "utilisateurs"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String)
    email = Column(String, unique=True, index=True)
    solde = Column(Float, default=0.0)

# Création automatique de la table sur Neon
Base.metadata.create_all(bind=engine)

# --- SCHÉMA DE DONNÉES (Pydantic) ---
class UtilisateurSchema(BaseModel):
    nom: str = Field(..., min_length=2)
    email: EmailStr
    solde: float = Field(default=0.0, ge=0)

    class Config:
        from_attributes = True # Permet à FastAPI de lire les objets de la base de données

# --- DÉPENDANCE ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- APPLICATION ---
app = FastAPI(
    title="API de gestion des utilisateurs",
    description="Connectée à PostgreSQL sur Neon.tech",
    version="1.0.0"
)

# 1. Le Contrôleur pour AJOUTER un utilisateur
@app.post("/utilisateurs/ajout", status_code=201)
def ajouter_utilisateur(user: UtilisateurSchema, db: Session = Depends(get_db)):
    # Vérification de l'unicité directement dans la base de données
    db_user = db.query(UtilisateurDB).filter(UtilisateurDB.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")
    
    # Création et enregistrement
    nouvel_utilisateur = UtilisateurDB(nom=user.nom, email=user.email, solde=user.solde)
    db.add(nouvel_utilisateur)
    db.commit() # Sauvegarde réelle sur Neon
    db.refresh(nouvel_utilisateur) # Récupère l'ID généré par la base
    
    return {"message": "New user added successfully to Neon !", "data": nouvel_utilisateur}

# 2. Le Contrôleur pour VOIR la liste
@app.get("/utilisateurs/lister")
def lister_utilisateurs(db: Session = Depends(get_db)):
    utilisateurs = db.query(UtilisateurDB).all()
    return utilisateurs

# 4. Le Contrôleur pour SUPPRIMER un utilisateur
@app.delete("/utilisateurs/{user_id}")
def supprimer_utilisateur(user_id: int, db: Session = Depends(get_db)):
    # On recherche l'utilisateur par son ID réel dans la table
    utilisateur = db.query(UtilisateurDB).filter(UtilisateurDB.id == user_id).first()
    
    if not utilisateur:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    # Suppression dans la base de données
    db.delete(utilisateur)
    db.commit() # Très important pour valider la suppression sur Neon
    
    return {"message": f"L'utilisateur {utilisateur.nom} a été supprimé avec succès"}

# 5. Le Contrôleur pour METTRE À JOUR le solde

# Import de tes schémas et de ta config DB
# (Assure-toi que UtilisateurDB, CompteDB et TransactionDB sont bien définis dans tes modèles)

app = FastAPI(title="API Banque Pro - Rinka")

# --- ROUTES UTILISATEURS ---

@app.patch("/utilisateurs/{user_id}")
def modifier_utilisateur_partiel(user_id: int, obj_update: UtilisateurUpdate, db: Session = Depends(get_db)):
    utilisateur = db.query(UtilisateurDB).filter(UtilisateurDB.id == user_id).first()
    if not utilisateur:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    donnees_maj = obj_update.dict(exclude_unset=True)

    if "email" in donnees_maj:
        email_existant = db.query(UtilisateurDB).filter(
            UtilisateurDB.email == donnees_maj["email"], 
            UtilisateurDB.id != user_id
        ).first()
        if email_existant:
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")

    for cle, valeur in donnees_maj.items():
        setattr(utilisateur, cle, valeur)

    db.commit()
    db.refresh(utilisateur)
    return {"message": "Profil mis à jour", "utilisateur": utilisateur}

# --- ROUTES COMPTES ---

@app.post("/comptes/", status_code=status.HTTP_201_CREATED)
def creer_compte(compte_data: CompteCreate, db: Session = Depends(get_db)):
    # Vérifier si l'utilisateur existe
    user = db.query(UtilisateurDB).filter(UtilisateurDB.id == compte_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur parent inexistant")

    # Génération d'un numéro de compte bancaire unique (Format Cameroun)
    num_compte = f"CM23-{random.randint(1000, 9999)}-{random.randint(10**7, 10**8-1)}"
    
    nouveau_compte = CompteDB(
        numero_compte=num_compte,
        type=compte_data.type_compte,
        solde=0.0,
        user_id=compte_data.user_id
    )
    
    db.add(nouveau_compte)
    db.commit()
    db.refresh(nouveau_compte)
    return nouveau_compte

# --- ROUTES TRANSACTIONS (Retrait / Dépôt) ---

@app.post("/transactions/{type_op}")
def effectuer_transaction(type_op: str, trans: TransactionCreate, db: Session = Depends(get_db)):
    # 1. Vérification du compte
    compte = db.query(CompteDB).filter(CompteDB.id == trans.compte_id).first()
    if not compte:
        raise HTTPException(status_code=404, detail="Compte bancaire introuvable")

    # 2. Logique métier
    if type_op.lower() == "retrait":
        if compte.solde < trans.montant:
            raise HTTPException(status_code=400, detail="Solde insuffisant pour ce retrait")
        compte.solde -= trans.montant
    elif type_op.lower() == "depot":
        compte.solde += trans.montant
    else:
        raise HTTPException(status_code=400, detail="Opération inconnue (utilisez 'depot' ou 'retrait')")

    # 3. Création de l'historique (Audit)
    historique = TransactionDB(
        montant=trans.montant,
        type=type_op.upper(),
        compte_id=compte.id,
        description=trans.description,
        reference=f"REF-{random.getrandbits(32)}"
    )

    db.add(historique)
    db.commit() # Sauvegarde le nouveau solde ET la transaction
    db.refresh(compte)

    return {
        "status": "success",
        "operation": type_op,
        "nouveau_solde": compte.solde,
        "reference": historique.reference
    }