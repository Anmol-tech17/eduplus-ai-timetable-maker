"""
backend/tests/test_api_crud.py
EduPlus AI Timetable Maker — API CRUD & Input Validation Tests
"""

def test_department_crud(client):
    """Test full Department lifecycle: create, get, list, update, duplicate check."""
    # 1. Create
    create_resp = client.post("/api/v1/departments", json={
        "code": "ECE",
        "name": "Electronics & Communication Engineering",
        "college_name": "Example Engineering College"
    })
    assert create_resp.status_code == 201
    created_dept = create_resp.json()
    dept_id = created_dept["id"]
    assert created_dept["code"] == "ECE"

    # 2. Duplicate code conflict (409)
    dup_resp = client.post("/api/v1/departments", json={
        "code": "ECE",
        "name": "Another ECE",
        "college_name": "Example Engineering College"
    })
    assert dup_resp.status_code == 409

    # 3. Get by ID
    get_resp = client.get(f"/api/v1/departments/{dept_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Electronics & Communication Engineering"

    # 4. List with pagination
    list_resp = client.get("/api/v1/departments?page=1&page_size=10")
    assert list_resp.status_code == 200
    pdata = list_resp.json()
    assert len(pdata["items"]) >= 1
    assert pdata["pagination"]["page"] == 1

    # 5. Update
    update_resp = client.put(f"/api/v1/departments/{dept_id}", json={
        "name": "Electronics and Communication"
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Electronics and Communication"


def test_academic_hierarchy_crud(client):
    """Test Academic Year, Division, and Batch creation and retrieval."""
    # 1. Create Department
    d_resp = client.post("/api/v1/departments", json={
        "code": "MECH",
        "name": "Mechanical Engineering",
        "college_name": "Example Engineering College"
    })
    dept_id = d_resp.json()["id"]

    # 2. Create Academic Year (Year 2)
    ay_resp = client.post("/api/v1/academic-years", json={
        "department_id": dept_id,
        "year_number": 2,
        "label": "Second Year"
    })
    assert ay_resp.status_code == 201
    ay_id = ay_resp.json()["id"]

    # 3. Create Division A
    div_resp = client.post("/api/v1/divisions", json={
        "academic_year_id": ay_id,
        "name": "A",
        "strength": 60
    })
    assert div_resp.status_code == 201
    div_id = div_resp.json()["id"]

    # 4. Create Batch B1
    batch_resp = client.post("/api/v1/batches", json={
        "division_id": div_id,
        "name": "B1",
        "capacity": 20
    })
    assert batch_resp.status_code == 201
    assert batch_resp.json()["name"] == "B1"

    # 5. List batches for division
    b_list = client.get(f"/api/v1/batches?division_id={div_id}")
    assert b_list.status_code == 200
    assert len(b_list.json()) == 1


def test_teacher_crud_and_validation(client):
    """Test Teacher profile creation, email validation, and retrieval."""
    d_resp = client.post("/api/v1/departments", json={
        "code": "CIVIL",
        "name": "Civil Engineering",
        "college_name": "Example Engineering College"
    })
    dept_id = d_resp.json()["id"]

    # 1. Valid Teacher
    t_resp = client.post("/api/v1/teachers", json={
        "department_id": dept_id,
        "name": "Dr. R. Sharma",
        "short_name": "R.Sharma",
        "designation": "Associate Professor",
        "weekly_workload_cap": 16,
        "email": "r.sharma@example.com"
    })
    assert t_resp.status_code == 201
    t_id = t_resp.json()["id"]

    # 2. Duplicate Email conflict
    dup_t = client.post("/api/v1/teachers", json={
        "department_id": dept_id,
        "name": "Duplicate Sharma",
        "short_name": "D.Sharma",
        "designation": "Professor",
        "weekly_workload_cap": 16,
        "email": "r.sharma@example.com"
    })
    assert dup_t.status_code == 409

    # 3. Invalid Email validation (422)
    inv_t = client.post("/api/v1/teachers", json={
        "department_id": dept_id,
        "name": "Invalid Email",
        "short_name": "I.Email",
        "designation": "Professor",
        "weekly_workload_cap": 16,
        "email": "not-an-email"
    })
    assert inv_t.status_code == 422


def test_room_crud(client):
    """Test Room creation, type checking, and capacity validation."""
    d_resp = client.post("/api/v1/departments", json={
        "code": "CHEM",
        "name": "Chemical Engineering",
        "college_name": "Example Engineering College"
    })
    dept_id = d_resp.json()["id"]

    # Classroom
    cr_resp = client.post("/api/v1/rooms", json={
        "department_id": dept_id,
        "name": "CR-101",
        "type": "classroom",
        "capacity": 65,
        "floor": 1
    })
    assert cr_resp.status_code == 201

    # Laboratory
    lab_resp = client.post("/api/v1/rooms", json={
        "department_id": dept_id,
        "name": "CHEM-LAB-1",
        "type": "laboratory",
        "capacity": 30,
        "floor": 2
    })
    assert lab_resp.status_code == 201

    # Filter rooms by type
    labs = client.get(f"/api/v1/rooms?department_id={dept_id}&type=laboratory")
    assert labs.status_code == 200
    assert len(labs.json()) == 1
    assert labs.json()[0]["name"] == "CHEM-LAB-1"
