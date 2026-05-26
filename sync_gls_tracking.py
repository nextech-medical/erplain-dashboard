# sync_gls_tracking.py
"""
Script complet de synchronisation des numéros de suivi GLS
"""
import argparse
from datetime import datetime
from extract_gls_tracking import extract_and_save_tracking
from gls_tracking_service import sync_gls_tracking_status

def sync_all(year=2026, limit_extract=500, limit_status=100):
    """
    Synchronisation complète:
    1. Extraction depuis ERPLAIN
    2. Mise à jour des statuts via API GLS
    """
    print("\n" + "=" * 70)
    print(f"🚀 SYNCHRONISATION COMPLÈTE GLS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Étape 1: Extraire les numéros de suivi
    tracking_data = extract_and_save_tracking(year, limit_extract)
    
    # Étape 2: Mettre à jour les statuts
    if tracking_data:
        status_updated = sync_gls_tracking_status(limit_status)
    else:
        status_updated = sync_gls_tracking_status(limit_status)
    
    # Résumé
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ DE SYNCHRONISATION")
    print("=" * 70)
    print(f"   📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   📦 BL analysés: {len(tracking_data) if tracking_data else 0}")
    print(f"   🏷️ Numéros extraits: {len(tracking_data) if tracking_data else 0}")
    print(f"   🔄 Statuts mis à jour: {status_updated}")
    print("=" * 70)
    
    return tracking_data, status_updated

def show_statistics():
    """Affiche les statistiques des numéros de suivi"""
    import psycopg2
    import pandas as pd
    from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 70)
    print("📊 STATISTIQUES DES NUMÉROS DE SUIVI GLS")
    print("=" * 70)
    
    # Stats globales
    df = pd.read_sql_query("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN status IS NOT NULL AND status != '' THEN 1 END) as avec_statut,
            COUNT(CASE WHEN status = 'delivered' THEN 1 END) as livre,
            COUNT(CASE WHEN status = 'in_transit' THEN 1 END) as en_cours,
            COUNT(CASE WHEN status = 'not_found' THEN 1 END) as non_trouve,
            COUNT(CASE WHEN last_event_date IS NOT NULL THEN 1 END) as avec_evenement
        FROM gls_tracking
    """, conn)
    
    print(f"\n📦 Total numéros: {df['total'].iloc[0]}")
    print(f"   📮 Avec statut: {df['avec_statut'].iloc[0]}")
    print(f"   ✅ Livrés: {df['livre'].iloc[0]}")
    print(f"   🚚 En cours: {df['en_cours'].iloc[0]}")
    print(f"   ❓ Non trouvés: {df['non_trouve'].iloc[0]}")
    
    # Derniers statuts
    df_recent = pd.read_sql_query("""
        SELECT order_number, tracking_number, status, last_event, last_sync
        FROM gls_tracking
        ORDER BY last_sync DESC
        LIMIT 20
    """, conn)
    
    if not df_recent.empty:
        print("\n📋 Derniers statuts:")
        print(df_recent.to_string(index=False))
    
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Synchronisation GLS Tracking')
    parser.add_argument('--action', choices=['extract', 'status', 'all', 'stats'], 
                       default='all', help='Action à exécuter')
    parser.add_argument('--year', type=int, default=2026, help='Année des BL')
    parser.add_argument('--limit-extract', type=int, default=500, help='Limite extraction BL')
    parser.add_argument('--limit-status', type=int, default=100, help='Limite mise à jour statut')
    
    args = parser.parse_args()
    
    if args.action == 'extract':
        extract_and_save_tracking(args.year, args.limit_extract)
    elif args.action == 'status':
        sync_gls_tracking_status(args.limit_status)
    elif args.action == 'all':
        sync_all(args.year, args.limit_extract, args.limit_status)
    elif args.action == 'stats':
        show_statistics()