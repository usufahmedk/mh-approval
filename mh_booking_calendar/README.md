# MH Booking Calendar

Custom booking calendar module for M&H Technical Services - handles Cleaning and Maintenance service scheduling.

## Features

- **Zone-Based Scheduling** - Organize bookings by service zones with capacity management
- **Automatic Booking Creation** - Bookings auto-created when Sales Order is confirmed
- **AMC Contract Support** - Integrates with sale_subscription for Annual Maintenance Contracts
- **Staff Assignment** - Assign employees (Cleaners, Technicians, Drivers) to bookings
- **Conflict Detection** - Prevents double-booking staff across zones and time slots
- **Calendar & Kanban Views** - Visual booking management with drag-and-drop
- **WhatsApp Notifications** - Send booking updates via WhatsApp

## Data Flow

```
Sales Order (confirmed)
    ↓
Booking (auto-created)
    ↓
Service Product (from SO line)
    ↓
Employee (staff assignment)
    ↓
Zone (service area)
```

## Dependencies

- `sale` - Sales management
- `sale_subscription` - AMC contracts
- `hr` - Employee management
- `calendar` - Scheduling
- `project` - Task integration
- `industry_fsm` - Field service

## Models

| Model | Description |
|-------|-------------|
| `mh.booking` | Main booking record linked to Sales Order |
| `mh.zone` | Service coverage areas |
| `mh.driver.team` | Driver team management |
| `mh.booking.conflict` | Staff conflict detection |

## Installation

1. Install the module from Apps
2. Configure zones in **M&H Booking > Zones**
3. Set up employee booking roles in **HR > Employees > Booking tab**
4. Create service products (type: Service) with booking duration

## Usage

1. Create a Sales Order with service products
2. Confirm the order - bookings are auto-created
3. Assign staff to bookings (auto-suggested based on zone)
4. Track booking status: Draft → Confirmed → In Progress → Completed

## Author

M&H Technical Services
