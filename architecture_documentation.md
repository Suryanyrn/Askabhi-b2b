# Askabhi-b2b Architecture Documentation

## 1. Overview
The Askabhi-b2b platform is a comprehensive Business-to-Business (B2B) logistics, operations, and inventory management application. It handles onboarding of companies, multi-tiered user roles (Admins, Managers, Drivers, Clients), warehouse and inventory tracking, and real-time shipment monitoring.

## 2. Technology Stack & Tools

### Backend Framework
- **Django (v6.0.6)**: Core web framework handling routing, ORM, security, and views.
- **Django Rest Framework (DRF)**: Powers the RESTful API endpoints.
- **Django Channels**: Enables WebSockets for real-time features (e.g., live tracking).
- **Daphne**: ASGI server used for production to handle both HTTP and WebSocket traffic concurrently.

### Database & Caching
- **PostgreSQL**: Primary relational database, hosted on Neon DB.
- **psycopg2-binary**: Postgres adapter for Python.
- **Redis (channels_redis)**: In-memory datastore acting as the channel layer backing for WebSockets and pub/sub capabilities.

### Authentication & Security
- **JWT (JSON Web Tokens)**: Used for API authentication via `djangorestframework_simplejwt`.
- **Session Auth**: Traditional session-based authentication for the web dashboard.
- **Python-dotenv**: Used for securely loading environment variables from `.env`.

### Storage & Static Files
- **Cloudinary**: Cloud storage for media files (e.g., profile pictures, delivery proofs) integrated via `django-cloudinary-storage`.
- **WhiteNoise**: Middleware for serving static files efficiently directly from the Django application in production.

### Deployment & Infrastructure
- **Docker**: Containerization using `python:3.12-slim` base images.
- **Render**: Target PaaS platform for hosting the backend containers.
- **Git/GitHub**: Source control and deployment triggers.

---

## 3. Application Structure (Apps)

The monolithic architecture is divided into 7 distinct Django apps based on bounded contexts:

1. **`onboarding`**: 
   - Handles the initial registration, company profile setup, and landing pages.
2. **`b2b_auth`**:
   - Contains custom authentication flows, JWT token generation, and password resets.
3. **`b2b_admin`**:
   - The primary dashboard for Company Admins.
   - Manages clients, drivers, managers, and gives an overarching view of operations.
4. **`b2b_manager`**:
   - Manager-specific dashboard and actions.
   - Handles audit logs (tracking who did what) and invitations.
5. **`b2b_driver`**:
   - Driver-facing interface for viewing assigned shipments, uploading proof of delivery, and transmitting GPS locations.
6. **`logistics`**:
   - Core inventory management.
   - Manages `Product`, `Warehouse`, `WarehouseStock`, and tracks changes via `InventoryLog`.
7. **`operations`**:
   - The heart of the supply chain workflows.
   - Manages `Order`, `OrderItem`, `Shipment`, and `Notification`.
   - Includes WebSocket consumers for real-time live map tracking.

---

## 4. Key Workflows

### A. Onboarding & Authentication Workflow
1. A new company registers via the `onboarding` app.
2. Admin invites Drivers and Managers via `b2b_admin`.
3. Users authenticate via the `b2b_auth` application. Web clients receive standard sessions while mobile/API clients receive JWT tokens.

### B. Logistics & Inventory Workflow
1. Admins/Managers define `Warehouses` and register `Products`.
2. Stock is added to `WarehouseStock`.
3. Any adjustments or fulfillment deductions automatically generate an `InventoryLog` for traceability.

### C. Order Fulfillment & Dispatch Workflow
1. A client places an `Order` (containing `OrderItems`) via the operations module.
2. The system dynamically deducts allocated inventory.
3. A Manager bundles the order into a `Shipment` and assigns it to a Driver.
4. The Driver logs into `b2b_driver`, reviews the shipment, and starts the delivery.

### D. Real-Time Tracking Workflow
1. While the Driver is out for delivery, their device transmits GPS coordinates to the server via WebSockets (`operations` app consumers).
2. Daphne and Redis broadcast these coordinates to the subscribed channels.
3. The Admin/Client tracking page receives the WebSocket payload and updates the vehicle's marker on the map in real-time.
4. Upon arrival, the Driver uploads a delivery proof (saved to Cloudinary) and marks the shipment as delivered.

---

## 5. Modules & Models Breakdown

- **Company Management**: `Company`
- **Users & Roles**: `Admin`, `Manager`, `Driver`, `Client`
- **Inventory**: `Product`, `Warehouse`, `WarehouseStock`, `InventoryLog`
- **Fulfillment**: `Order`, `OrderItem`, `Shipment`
- **System**: `AuditLog`, `Notification`

## 6. Development Guidelines
- **Static Files**: Run `python manage.py collectstatic` to gather CSS/JS. WhiteNoise serves these files locally (even with `DEBUG=False`) and in production.
- **Migrations**: Since it's a production-ready Postgres database, never manually alter primary key types (e.g., BigInt to UUID) without complete data migrations.
- **Environment Variables**: Always define required keys (`SECRET_KEY`, `DATABASE_URL`, `CLOUDINARY_*`) in a `.env` file before starting the server.
