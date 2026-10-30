import os
import sys
import sqlite3
import pytest

# إضافة المجلد الرئيسي للمشروع إلى مسار بايثون
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.seed_data import seed_database, DB_PATH, get_connection


@pytest.fixture(scope="module")
def seeded_db():
    """تشغيل الـ seed قبل الاختبارات للتأكد من وجود البيانات"""
    seed_database(DB_PATH)
    conn = get_connection(DB_PATH)
    yield conn
    conn.close()


def test_locations_count_and_types(seeded_db):
    """التحقق من عدد المواقع وأنواعها (Depot, Hub, Customer)"""
    cursor = seeded_db.cursor()
    cursor.execute("SELECT kind, COUNT(*) FROM locations GROUP BY kind;")
    counts = dict(cursor.fetchall())

    assert counts.get("DEPOT", 0) >= 1, "Must have at least 1 DEPOT"
    assert counts.get("HUB", 0) >= 2, "Must have at least 2 HUBs"
    assert counts.get("CUSTOMER", 0) >= 17, "Must have at least 17 CUSTOMERs"

    cursor.execute("SELECT COUNT(*) FROM locations;")
    total_locations = cursor.fetchone()[0]
    assert total_locations >= 20, "Total locations must be >= 20"


def test_roads_count_and_special_rules(seeded_db):
    """التحقق من عدد الطرق ووجود طرق باتجاه واحد وطرق مغلقة"""
    cursor = seeded_db.cursor()

    cursor.execute("SELECT COUNT(*) FROM roads;")
    total_roads = cursor.fetchone()[0]
    assert total_roads >= 35, "Total roads must be >= 35"

    cursor.execute("SELECT COUNT(*) FROM roads WHERE is_one_way = 1;")
    one_way_count = cursor.fetchone()[0]
    assert one_way_count >= 2, "Must have at least 2 one-way roads"

    cursor.execute("SELECT COUNT(*) FROM roads WHERE is_closed = 1;")
    closed_count = cursor.fetchone()[0]
    assert closed_count >= 1, "Must have at least 1 closed road"


def test_isolated_node_exists(seeded_db):
    """التحقق من وجود عميل معزول لا تصله أي طرق لحالات اختبار الفشل"""
    cursor = seeded_db.cursor()
    cursor.execute("SELECT id FROM locations WHERE code = 'CUST_ISOLATED';")
    row = cursor.fetchone()
    assert row is not None, "CUST_ISOLATED must exist"

    isolated_id = row[0]
    cursor.execute(
        "SELECT COUNT(*) FROM roads WHERE from_id = ? OR to_id = ?;",
        (isolated_id, isolated_id)
    )
    road_connections = cursor.fetchone()[0]
    assert road_connections == 0, "CUST_ISOLATED should have 0 connected roads"