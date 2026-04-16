from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
    
# --- CONFIGURATION NEON ---
DATABASE_URL = "postgresql://neondb_owner:npg_9yeuACYm2IVE@ep-wispy-sky-ab3hlsyl.eu-west-2.aws.neon.tech/neondb?sslmode=require"

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




# 4. Le Contrôleur pour SUPPRIMER un utilisateur par email
"""
@app.delete("/utilisateurs/{user_id}")
def supprimer_utilisateur(user_id: int):
    if user_id < len(base_de_donnees):
        utilisateur_supprime = base_de_donnees.pop(user_id)
        return {"message": f"L'utilisateur {utilisateur_supprime['nom']} a été supprimé"}
    
    return {"erreur": "Utilisateur non trouvé"}

# 5. Le Contrôleur pour METTRE À JOUR un utilisateur par email
@app.put("/utilisateurs/{user_id}")
def mettre_a_jour_solde(user_id: int, nouveau_solde: float):
    # On vérifie si l'indice existe dans notre liste
    if user_id < len(base_de_donnees):
        base_de_donnees[user_id]["solde"] = nouveau_solde
        return {"message": "Solde mis à jour", "user": base_de_donnees[user_id]}
    
    return {"erreur": "Utilisateur non trouvé"}
"""