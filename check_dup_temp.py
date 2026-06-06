import pymysql
import sys

try:
    conn = pymysql.connect(host='localhost', port=3306, user='root', password='bini_health_2026', database='bini_health', charset='utf8mb4')
    c = conn.cursor()
    print("connected ok")
    
    print("=== 各级别统计 ===")
    c.execute("SELECT level, COUNT(*) as cnt FROM brain_game_regions GROUP BY level ORDER BY FIELD(level, 'province','city','district','street')")
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]} 条")
    
    print()
    print("=== 同名同级别重复 ===")
    c.execute("SELECT level, name, COUNT(*) as cnt, GROUP_CONCAT(id ORDER BY id) as ids FROM brain_game_regions GROUP BY level, name HAVING cnt > 1 ORDER BY cnt DESC")
    dupes = c.fetchall()
    if dupes:
        for row in dupes:
            print(f"  [{row[0]}] {row[1]}: {row[2]} 条, IDs: {row[3]}")
        print(f"共 {len(dupes)} 组重复")
    else:
        print("  无重复")
    
    print()
    print("=== 同名+同级别+同父级重复 ===")
    c.execute("SELECT level, name, parent_adcode, COUNT(*) as cnt, GROUP_CONCAT(id ORDER BY id) as ids FROM brain_game_regions GROUP BY level, name, parent_adcode HAVING cnt > 1 ORDER BY cnt DESC")
    dupes2 = c.fetchall()
    if dupes2:
        for row in dupes2:
            print(f"  [{row[0]}] {row[1]} (parent={row[2]}): {row[3]} 条, IDs: {row[4]}")
        print(f"共 {len(dupes2)} 组重复")
    else:
        print("  无重复")
    
    c.close()
    conn.close()
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
