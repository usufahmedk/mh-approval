
from odoo import fields, models, Command, api
import pytz
from dateutil import rrule
from datetime import timedelta, datetime, time
from babel.dates import format_time
from odoo.tools.misc import babel_locale_parse, get_lang

class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    booking_type = fields.Selection([
        ('individual', 'Individual Booking'),
        ('team_booking', 'Multi-Member Booking'),
        ('multi_team_booking', 'Team Booking')
    ], string="Booking Type", default='individual')
    
    assignee_required = fields.Boolean("Team Booking", compute='_compute_assignee_required', store=True,
                                      help="Deprecated: Use booking_type dropdown instead")
    
    required_users_count = fields.Integer("Required Members for Inspection", default=1,
                                        help="Number of staff members required for multi-member booking (minimum users needed from available staff)")
    
    team_ids = fields.Many2many('appointment.team', string="Teams", 
                               help="Teams available for team booking")
    
    price_based_on_sq_ft = fields.Boolean("Price based on Sq ft?")
    
    slot_interval_minutes = fields.Float(
        string="Generate Slots Every",
        help="Create booking slots at regular intervals (e.g., 0:15 = every 15 minutes, 0:30 = every 30 minutes). If not set, uses default behavior."
    )
    
    @api.depends('booking_type')
    def _compute_assignee_required(self):
        for record in self:
            record.assignee_required = False
    
    @api.onchange('booking_type')
    def _onchange_booking_type(self):
        if self.booking_type == 'individual':
            self.required_users_count = 1
            self.team_ids = [(5, 0, 0)]
        elif self.booking_type == 'team_booking':
            if not self.required_users_count or self.required_users_count < 1:
                self.required_users_count = 1
    
    @api.onchange('team_ids')
    def _onchange_team_ids(self):
        if self.booking_type == 'multi_team_booking' and self.team_ids:
            all_team_users = self.env['res.users']
            for team in self.team_ids:
                all_team_users |= team.user_ids
            if all_team_users:
                self.staff_user_ids = [(6, 0, all_team_users.ids)]
    
    def _prepare_calendar_event_values(
        self, asked_capacity, booking_line_values, duration,
        appointment_invite, guests, name, customer, staff_user, start, stop
    ):
        self.ensure_one()
        result = super(AppointmentType,self)._prepare_calendar_event_values(
            asked_capacity, booking_line_values, duration, appointment_invite, 
            guests, name, customer, staff_user, start, stop
        )
        
        if self.booking_type in ['team_booking', 'multi_team_booking']:
            existing_appointment = self.env['calendar.event'].search([
                ('name', '=', name),
                ('start', '=', start),
                ('stop', '=', stop),
                ('appointment_type_id', '=', self.id)
            ], limit=1)
            
            if existing_appointment:
                return result
            from odoo.exceptions import ValidationError

            try:
                availability_values = self._get_availability_values(start, stop)
            except AttributeError:
                availability_values = {}
            
            validation_result = self._validate_booking_availability(start, stop, availability_values)

            if not validation_result['is_available']:
                raise ValidationError(validation_result['error_message'])

            assigned_team_members = validation_result['available_team_members']
            suggested_organizer = validation_result['suggested_organizer']
            if assigned_team_members and suggested_organizer:
                organizer_user = suggested_organizer
                if staff_user and staff_user in assigned_team_members:
                    organizer_user = staff_user
                
                result['user_id'] = organizer_user.id
            else:
                raise ValidationError("No team members available for booking. Please refresh and select a different time slot.")
            attendee_partners = assigned_team_members.mapped('partner_id') | customer
            safe_guests = guests if guests else self.env['res.partner']
            attendee_values = [Command.create({'partner_id': pid, 'state': 'accepted'}) for pid in attendee_partners.ids] + \
            [Command.create({'partner_id': guest.id}) for guest in safe_guests - attendee_partners if guest]
            
            result['attendee_ids'] = attendee_values
            result['partner_ids'] = [Command.link(pid) for pid in (attendee_partners | safe_guests).ids]
            booking_type_info = self._get_booking_type_description_with_team(assigned_team_members)
            if booking_type_info:
                current_description = result.get('description', '')
                result['description'] = f"{current_description}\n\n{booking_type_info}".strip()
        
        return result
    
    def get_available_organizer_for_slot(self, start, stop):
        """
        Get the best available organizer for a given time slot
        This method can be called from frontend to refresh organizer selection
        
        :param datetime start: Slot start time
        :param datetime stop: Slot stop time  
        :return: dict with organizer info or error
        """
        if self.booking_type == 'multi_team_booking':
            available_team_members = self.get_available_users_for_booking(start, stop, {})
            
            if available_team_members:
                organizer = available_team_members[0]
                
                return {
                    'success': True,
                    'organizer_id': organizer.id,
                    'organizer_name': organizer.name,
                    'team_members': [{'id': user.id, 'name': user.name} for user in available_team_members],
                    'message': f"Organizer updated to {organizer.name}"
                }
            else:
                return {
                    'success': False,
                    'error': 'No available team members for this time slot',
                    'message': 'Please select a different time slot'
                }
        else:
            if self.staff_user_ids:
                organizer = self.staff_user_ids[0]
                return {
                    'success': True,
                    'organizer_id': organizer.id,
                    'organizer_name': organizer.name,
                    'message': f"Organizer: {organizer.name}"
                }
        
        return {
            'success': False,
            'error': 'No organizer available',
            'message': 'Please refresh and try again'
        }
    
    def _get_assigned_users_for_event(self, start, stop, preferred_staff_user=None):
        """
        Get the users that should be assigned to the calendar event
        based on the booking type and availability
        """
        if self.booking_type == 'team_booking':
            available_users = self.env['res.users']
            required_count = self.required_users_count or 1
            
            if preferred_staff_user and preferred_staff_user in self.staff_user_ids:
                available_users |= preferred_staff_user
                required_count -= 1
            
            for staff_user in self.staff_user_ids:
                if staff_user != preferred_staff_user and len(available_users) < (self.required_users_count or 1):
                    available_users |= staff_user
            
            return available_users
            
        elif self.booking_type == 'multi_team_booking':
            try:
                availability_values = self._get_availability_values(start, stop)
            except AttributeError:
                availability_values = {}
            
            selected_users = self.get_available_users_for_booking(start, stop, availability_values)
            return selected_users
            
        else:
            return self.staff_user_ids
    
    def _get_booking_type_description(self):
        """Get description text based on booking type - DEPRECATED: Use _get_booking_type_description_with_team"""
        if self.booking_type == 'team_booking':
            return f"Multi-Member Booking: {self.required_users_count} staff member(s) assigned for inspection."
        elif self.booking_type == 'multi_team_booking':
            team_names = ', '.join(team.name for team in self.team_ids)
            return f"Team Booking: Complete team assigned from available teams ({team_names})."
        return ""
    
    def _get_booking_type_description_with_team(self, assigned_users):
        """Get description text showing the actual selected team members"""
        if self.booking_type == 'team_booking':
            return f"Multi-Member Booking: {len(assigned_users)} staff member(s) assigned for inspection: {', '.join(user.name for user in assigned_users)}"
        elif self.booking_type == 'multi_team_booking':
            if assigned_users:
                selected_team = None
                for team in self.team_ids:
                    team_user_ids = set(team.user_ids.ids)
                    assigned_user_ids = set(assigned_users.ids)
                    
                    if assigned_user_ids.issubset(team_user_ids) and len(assigned_user_ids) == len(team_user_ids):
                        selected_team = team
                        break
                
                if selected_team:
                    return f"Team Booking: {selected_team.name} assigned ({', '.join(user.name for user in assigned_users)})"
                else:
                    return f"Team Booking: Custom team assigned ({', '.join(user.name for user in assigned_users)})"
            else:
                return f"Team Booking: No team members assigned"
        return ""
    
    def _slots_available(self, slots, staff_user, availability_values):
        """Override main slots filtering for enhanced booking logic with dynamic organizer"""
        start_dt = min(slot['UTC'][0] for slot in slots) if slots else datetime.now()
        end_dt = max(slot['UTC'][1] for slot in slots) if slots else datetime.now()
        
        if self.booking_type == 'individual':
            self._slots_fill_individual_availability(slots, start_dt, end_dt)
        elif self.booking_type == 'team_booking':
            self._slots_fill_multi_member_availability(slots, start_dt, end_dt)
        elif self.booking_type == 'multi_team_booking':
            self._slots_fill_team_availability(slots, start_dt, end_dt)
        else:
            self._slots_fill_individual_availability(slots, start_dt, end_dt)
        
        available_slots = []
        for slot in slots:
            has_staff_assignment = slot.get('staff_user_id') or slot.get('available_staff_users')

            if has_staff_assignment:

                if self.booking_type == 'multi_team_booking' and slot.get('staff_user_id'):
                    slot_start = slot['UTC'][0]
                    slot_end = slot['UTC'][1]
                    available_team = self.get_available_users_for_booking(slot_start, slot_end, availability_values)

                    if available_team:

                        dynamic_organizer = available_team[0]
                        slot['dynamic_organizer_id'] = dynamic_organizer.id
                        slot['dynamic_organizer_name'] = dynamic_organizer.name
                        slot['available_team'] = [{'id': u.id, 'name': u.name} for u in available_team]
                if not slot.get('staff_user_id') and slot.get('available_staff_users'):

                    available_users = slot.get('available_staff_users')
                    if available_users:
                        slot['staff_user_id'] = available_users[0] if hasattr(available_users, '__iter__') else available_users

                available_slots.append(slot)

        return available_slots
    
    def _slot_availability_is_user_available(self, slot, staff_user, availability_values):
        """ Enhanced method that handles different booking types:
        - Individual: Original Odoo logic
        - Multi-Member Booking: Check if minimum required staff members are available
        - Team Booking: Check if complete teams are available

        :param dict slot: a slot as generated by ``_slots_generate``;
        :param <res.users> staff_user: user to check against slot boundaries.
        :param dict availability_values: dict of data used for availability check.
        :return: boolean: is slot available for booking
        """
        if self.booking_type == 'team_booking':
            return self._check_multi_member_booking_availability(slot, availability_values)
        elif self.booking_type == 'multi_team_booking':
            return self._check_team_booking_availability(slot, availability_values)
        else:
            return super(AppointmentType,self)._slot_availability_is_user_available(slot, staff_user, availability_values)
    
    def _check_multi_member_booking_availability(self, slot, availability_values):
        """
        Check if minimum required users from staff are available for multi-member booking
        
        :param dict slot: slot information
        :param dict availability_values: availability data
        :return: boolean
        """
        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
        available_users_count = 0
        required_count = self.required_users_count or 1
        

        for staff_user in self.staff_user_ids:
            if self._is_single_user_available(staff_user, slot_start_dt_utc, slot_end_dt_utc, slot, availability_values):
                available_users_count += 1
                

                if available_users_count >= required_count:
                    return True
        
        return available_users_count >= required_count
    
    def _check_team_booking_availability(self, slot, availability_values):
        """
        Check if at least one complete team is available for team booking
        
        :param dict slot: slot information  
        :param dict availability_values: availability data
        :return: boolean
        """
        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
        
        if not self.team_ids:
            return False
        

        for team in self.team_ids:
            available_users = team.get_available_users_for_slot(
                slot_start_dt_utc, slot_end_dt_utc, availability_values
            )
            

            if len(available_users) == len(team.user_ids):
                return True
        
        return False
    
    def _check_legacy_team_booking_availability(self, slot, availability_values):
        """
        Legacy team booking logic (all users must be available)
        Kept for backward compatibility
        """
        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
        
        for staff_user in self.staff_user_ids:
            if not self._is_single_user_available(staff_user, slot_start_dt_utc, slot_end_dt_utc, slot, availability_values):
                return False
        return True
    
    def _is_single_user_available(self, staff_user, slot_start_dt_utc, slot_end_dt_utc, slot, availability_values):
        """
        Check if a single user is available for the given slot
        
        :param res.users staff_user: user to check
        :param datetime slot_start_dt_utc: slot start time in UTC
        :param datetime slot_end_dt_utc: slot end time in UTC 
        :param dict slot: slot information
        :param dict availability_values: availability data
        :return: boolean
        """
        staff_user_tz = pytz.timezone(staff_user.tz) if staff_user.tz else pytz.utc
        slot_start_dt_user_timezone = slot_start_dt_utc.astimezone(staff_user_tz)
        slot_end_dt_user_timezone = slot_end_dt_utc.astimezone(staff_user_tz)
        if slot and slot.get('slot') and hasattr(slot['slot'], 'restrict_to_user_ids'):
            if slot['slot'].restrict_to_user_ids and staff_user not in slot['slot'].restrict_to_user_ids:
                return False

        partner_to_events = availability_values.get('partner_to_events') or {}
        if partner_to_events.get(staff_user.partner_id):
            for day_dt in rrule.rrule(freq=rrule.DAILY,
                                      dtstart=slot_start_dt_utc,
                                      until=slot_end_dt_utc,
                                      interval=1):
                day_events = partner_to_events[staff_user.partner_id].get(day_dt.date()) or []
                if any(not event.allday and (event.start < slot_end_dt_utc and event.stop > slot_start_dt_utc) for event in day_events):
                    return False
            for day_dt in rrule.rrule(freq=rrule.DAILY,
                                      dtstart=slot_start_dt_user_timezone,
                                      until=slot_end_dt_user_timezone,
                                      interval=1):
                day_events = partner_to_events[staff_user.partner_id].get(day_dt.date()) or []
                if any(event.allday for event in day_events):
                    return False
        return True
    
    def _check_user_availability_simple(self, staff_user, slot_start_dt_utc, slot_end_dt_utc, availability_values):
        """
        Enhanced user availability check that includes ALL calendar events
        
        :param res.users staff_user: user to check
        :param datetime slot_start_dt_utc: slot start time in UTC
        :param datetime slot_end_dt_utc: slot end time in UTC 
        :param dict availability_values: availability data
        :return: boolean
        """

        all_events = self.env['calendar.event'].search([
            ('partner_ids', 'in', staff_user.partner_id.id),
            '|',
            '&', ('start', '<', slot_end_dt_utc), ('stop', '>', slot_start_dt_utc),  # Overlapping events
            '&', ('allday', '=', True), ('start_date', '=', slot_start_dt_utc.date())  # All-day events
        ])
        
        for event in all_events:
            if event.allday:
                return False
            else:
                if event.start < slot_end_dt_utc and event.stop > slot_start_dt_utc:
                    return False
        
        return True
    
    def get_available_users_for_booking(self, slot_start_utc, slot_end_utc, availability_values):
        """
        Get the users that should be booked for this appointment based on booking type
        
        :param datetime slot_start_utc: slot start time in UTC
        :param datetime slot_end_utc: slot end time in UTC
        :param dict availability_values: availability data
        :return: recordset of users to book
        """
        if self.booking_type == 'team_booking':
            return self._get_users_for_multi_member_booking(slot_start_utc, slot_end_utc, availability_values)
        elif self.booking_type == 'multi_team_booking':
            return self._get_users_for_team_booking(slot_start_utc, slot_end_utc, availability_values)
        else:

            return self.staff_user_ids
    
    def _get_users_for_multi_member_booking(self, slot_start_utc, slot_end_utc, availability_values):
        """Get optimal users for multi-member booking based on required count"""
        available_users = self.env['res.users']
        required_count = self.required_users_count or 1
        
        for staff_user in self.staff_user_ids:
            if self._check_user_availability_simple(staff_user, slot_start_utc, slot_end_utc, availability_values):
                available_users |= staff_user
                if len(available_users) >= required_count:
                    break
        
        return available_users[:required_count] if available_users else self.env['res.users']
    
    def _get_users_for_team_booking(self, slot_start_utc, slot_end_utc, availability_values):
        """Get users from the optimal team based on availability overlap"""

        all_available_users = self.env['res.users']
        for staff_user in self.staff_user_ids:
            if self._check_user_availability_simple(staff_user, slot_start_utc, slot_end_utc, availability_values):
                all_available_users |= staff_user
        
        if not all_available_users:
            return self.env['res.users']
        

        for team in self.team_ids:
            team_users_set = set(team.user_ids.ids)
            available_users_set = set(all_available_users.ids)
            

            if available_users_set.issubset(team_users_set) and len(available_users_set) == len(team_users_set):
                return team.user_ids
        


        teams_by_size = sorted(self.team_ids, key=lambda t: len(t.user_ids), reverse=True)
        
        for team in teams_by_size:

            available_members = []
            
            for member in team.user_ids:

                is_available = self._check_user_availability_simple(member, slot_start_utc, slot_end_utc, availability_values)
                
                if is_available:
                    available_members.append(member)
            

            if len(available_members) == len(team.user_ids):
                return team.user_ids
        


        best_overlap_team = None
        best_overlap_count = 0
        
        for team in self.team_ids:
            team_users_set = set(team.user_ids.ids)
            available_users_set = set(all_available_users.ids)
            overlap = team_users_set.intersection(available_users_set)
            
            if len(overlap) > best_overlap_count:
                best_overlap_count = len(overlap)
                best_overlap_team = team
        
        if best_overlap_team and best_overlap_count > 0:

            overlap_user_ids = set(best_overlap_team.user_ids.ids).intersection(set(all_available_users.ids))
            return self.env['res.users'].browse(list(overlap_user_ids))
        
        return self.env['res.users']
    
    def _validate_booking_availability(self, start, stop, availability_values=None):
        """
        Real-time validation of team availability at booking time
        Prevents race conditions between slot selection and booking attempt
        
        :param datetime start: Booking start time in UTC
        :param datetime stop: Booking stop time in UTC  
        :param dict availability_values: Availability data (optional)
        :return: dict with validation result and available team members
        """
        if availability_values is None:
            availability_values = {}
            
        result = {
            'is_available': False,
            'available_team_members': self.env['res.users'],
            'error_message': '',
            'suggested_organizer': None
        }
        
        if self.booking_type == 'multi_team_booking':

            available_team_members = self.get_available_users_for_booking(start, stop, availability_values)
            
            if available_team_members:
                result['is_available'] = True
                result['available_team_members'] = available_team_members
                result['suggested_organizer'] = available_team_members[0]
            else:
                result['error_message'] = "No complete teams are available for the selected time slot. Please refresh and select a different time."
                
        elif self.booking_type == 'team_booking':

            available_users = self.env['res.users']
            required_count = self.required_users_count or 1
            
            for staff_user in self.staff_user_ids:
                if self._check_user_availability_simple(staff_user, start, stop, availability_values):
                    available_users |= staff_user
                    if len(available_users) >= required_count:
                        break
            
            if len(available_users) >= required_count:
                result['is_available'] = True
                result['available_team_members'] = available_users[:required_count]
                result['suggested_organizer'] = available_users[0]
            else:
                result['error_message'] = f"Only {len(available_users)} out of {required_count} required team members are available. Please refresh and select a different time."
        else:

            if self.staff_user_ids:

                for staff_user in self.staff_user_ids:
                    if self._check_user_availability_simple(staff_user, start, stop, availability_values):
                        result['is_available'] = True
                        result['available_team_members'] = staff_user
                        result['suggested_organizer'] = staff_user
                        break
                
                if not result['is_available']:
                    result['error_message'] = "Staff member is no longer available for the selected time slot. Please refresh and select a different time."
        
        return result
    
    def _slots_generate(self, first_day, last_day, timezone, reference_date=None):
        """Override slot generation for custom intervals while preserving default functionality"""

        if not self.slot_interval_minutes or self.slot_interval_minutes <= 0:

            basic_slots = super()._slots_generate(first_day, last_day, timezone, reference_date)
            return self._apply_booking_type_availability(basic_slots, timezone)
        return self._generate_custom_interval_slots_core(first_day, last_day, timezone, reference_date)

    def _generate_custom_interval_slots_core(self, first_day, last_day, timezone, reference_date=None):
        """Generate slots with custom intervals and apply booking type availability"""

        basic_slots = self._generate_basic_custom_slots(first_day, last_day, timezone, reference_date)
        

        return self._apply_booking_type_availability(basic_slots, timezone)

    def _generate_basic_custom_slots(self, first_day, last_day, timezone, reference_date=None):
        """Generate basic slots using Odoo's core logic but with custom intervals"""

        if not reference_date:
            reference_date = datetime.utcnow()
            
        appt_tz = pytz.timezone(self.appointment_tz)
        requested_tz = pytz.timezone(timezone)
        end_tz_apt_type = self.end_datetime.astimezone(appt_tz) if self.category == 'punctual' else False
        ref_tz_apt_type = reference_date.astimezone(appt_tz)
        now_tz_apt_type = datetime.utcnow().astimezone(appt_tz)
        slots = []
        ref_start = ref_tz_apt_type
        if ref_start <= (now_tz_apt_type + timedelta(hours=self.min_schedule_hours)):
            ref_start += timedelta(hours=self.min_schedule_hours)

        def append_slot_with_custom_interval(day, slot):
            """Modified version of Odoo's append_slot function with custom intervals"""
            local_start = appt_tz.localize(
                datetime.combine(day,
                                 time(hour=int(slot.start_hour),
                                      minute=int(round((slot.start_hour % 1) * 60))
                                     )
                                )
            )
            

            while local_start < ref_start:
                local_start += timedelta(hours=self.appointment_duration)

            local_end = local_start + timedelta(hours=self.appointment_duration)
            

            local_slot_end = appt_tz.localize(
                day.replace(hour=0, minute=0, second=0) +
                timedelta(hours=slot._convert_end_hour_24_format())
            )
            

            if end_tz_apt_type and local_start.date() == end_tz_apt_type.date() and local_slot_end > end_tz_apt_type:
                local_slot_end = end_tz_apt_type
            custom_interval_hours = self.slot_interval_minutes
            current_start = local_start
            
            while current_start + timedelta(hours=self.appointment_duration) <= local_slot_end:
                current_end = current_start + timedelta(hours=self.appointment_duration)
                
                slots.append({
                    self.appointment_tz: (current_start, current_end),
                    timezone: (
                        current_start.astimezone(requested_tz),
                        current_end.astimezone(requested_tz),
                    ),
                    'UTC': (
                        current_start.astimezone(pytz.UTC).replace(tzinfo=None),
                        current_end.astimezone(pytz.UTC).replace(tzinfo=None),
                    ),
                    'slot': slot,
                })
                

                current_start += timedelta(hours=custom_interval_hours)
        if self.category != 'custom':

            if last_day < reference_date.astimezone(pytz.UTC):
                return slots
            from dateutil import rrule
            slot_weekday = [int(weekday) - 1 for weekday in self.slot_ids.mapped('weekday')]
            
            for day in rrule.rrule(rrule.DAILY,
                                dtstart=first_day.astimezone(appt_tz).date(),
                                until=last_day.astimezone(appt_tz).date(),
                                byweekday=slot_weekday):
                for slot in self.slot_ids.filtered(lambda x: int(x.weekday) == day.isoweekday()):
                    append_slot_with_custom_interval(day, slot)
        else:

            unique_slots = self.slot_ids.filtered(lambda slot: slot.slot_type == 'unique' and slot.end_datetime > reference_date)

            for slot in unique_slots:
                start = slot.start_datetime.astimezone(tz=None)
                end = slot.end_datetime.astimezone(tz=None)
                startUTC = start.astimezone(pytz.UTC).replace(tzinfo=None)
                endUTC = end.astimezone(pytz.UTC).replace(tzinfo=None)
                slots.append({
                    self.appointment_tz: (start.astimezone(appt_tz), end.astimezone(appt_tz)),
                    timezone: (start.astimezone(requested_tz), end.astimezone(requested_tz)),
                    'UTC': (startUTC, endUTC),
                    'slot': slot,
                })
        
        return slots

    def _apply_booking_type_availability(self, slots, timezone):
        """Apply enhanced booking type availability checking using Odoo's native system"""
        if not slots:
            return slots
        

        start_dt = min(slot['UTC'][0] for slot in slots)
        end_dt = max(slot['UTC'][1] for slot in slots)
        


        if self.booking_type == 'individual':
            self._slots_fill_individual_availability(slots, start_dt, end_dt)
        elif self.booking_type == 'team_booking':
            self._slots_fill_multi_member_availability(slots, start_dt, end_dt)
        elif self.booking_type == 'multi_team_booking':
            self._slots_fill_team_availability(slots, start_dt, end_dt)
        else:
            self._slots_fill_individual_availability(slots, start_dt, end_dt)
        

        available_slots = []
        
        for slot in slots:

            if slot.get('staff_user_id') or slot.get('available_staff_users'):
                available_slots.append(slot)
        
        return available_slots

    def _count_available_staff_for_slot(self, slot):
        """Count how many staff members are actually available for this slot"""
        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
        available_count = 0
        
        for staff_user in self.staff_user_ids:

            if staff_user.partner_id.calendar_verify_availability(slot_start_dt_utc, slot_end_dt_utc):
                available_count += 1
        
        return available_count

    def _get_multiple_staff_for_slot(self, slot, required_count):
        """Get multiple available staff members for multi-member booking"""
        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
        available_staff = []
        
        for staff_user in self.staff_user_ids:

            if staff_user.partner_id.calendar_verify_availability(slot_start_dt_utc, slot_end_dt_utc):
                available_staff.append(staff_user)
                

                if len(available_staff) >= required_count:
                    break
        
        return self.env['res.users'].browse([u.id for u in available_staff])

    def _slots_fill_individual_availability(self, slots, start_dt, end_dt):
        """Fill slots with individual booking availability - staff-level availability checking"""
        for slot in slots:
            slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
            available_staff = []
            for staff_user in self.staff_user_ids:
                if self._check_staff_calendar_availability(staff_user, slot_start_dt_utc, slot_end_dt_utc):
                    available_staff.append(staff_user)

            if available_staff:

                slot['staff_user_id'] = available_staff[0]
                slot['available_staff_users'] = self.env['res.users'].browse([u.id for u in available_staff])
    def _slots_fill_multi_member_availability(self, slots, start_dt, end_dt):
        """Fill slots with multi-member booking availability - staff-level availability checking"""
        for slot in slots:
            slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
            available_staff = []
            

            for staff_user in self.staff_user_ids:
                if self._check_staff_calendar_availability(staff_user, slot_start_dt_utc, slot_end_dt_utc):
                    available_staff.append(staff_user)
            

            required_count = self.required_users_count or 1
            if len(available_staff) >= required_count:

                slot['available_staff_users'] = self.env['res.users'].browse([u.id for u in available_staff[:required_count]])
                slot['staff_user_id'] = available_staff[0]  # Primary staff member
    def _slots_fill_team_availability(self, slots, start_dt, end_dt):
        """Fill slots with team booking availability - staff-level availability with team logic"""
        for slot in slots:
            slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
            


            if self._check_team_booking_availability(slot, {}):

                team_users = self._get_users_for_team_booking(slot_start_dt_utc, slot_end_dt_utc, {})
                if team_users:

                    slot['available_staff_users'] = team_users
                    slot['staff_user_id'] = team_users[0]
    def _check_staff_calendar_availability(self, staff_user, start_dt, end_dt):
        """
        Check if a specific staff member has calendar availability (no conflicts from ANY source)
        This replaces appointment-level conflict checking with proper staff-level checking
        """

        conflicting_events = self.env['calendar.event'].search([
            ('partner_ids', 'in', staff_user.partner_id.id),
            '|',

            '&', ('start', '<', end_dt), ('stop', '>', start_dt),

            '&', ('allday', '=', True), ('start_date', '=', start_dt.date()),

            ('active', '=', True),
        ])
        

        return len(conflicting_events) == 0

    def _slots_fill_users_availability(self, slots, first_day, last_day, staff_users=None):
        """
        Override Odoo's core slot filling method to use our custom booking type logic
        This method is called by _get_appointment_slots and must use our enhanced logic
        """

        if self.booking_type == 'individual':
            self._slots_fill_individual_availability(slots, first_day, last_day)
        elif self.booking_type == 'team_booking':
            self._slots_fill_multi_member_availability(slots, first_day, last_day)
        elif self.booking_type == 'multi_team_booking':
            self._slots_fill_team_availability(slots, first_day, last_day)
        else:
            self._slots_fill_individual_availability(slots, first_day, last_day)

    def _check_individual_availability(self, slot, availability_values):
        """Check if any single staff member is available for individual booking"""
        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
        
        for staff_user in self.staff_user_ids:
            if self._is_user_available_for_slot(staff_user, slot_start_dt_utc, slot_end_dt_utc, availability_values):

                slot['staff_user_id'] = staff_user
                return True
        
        return False

    def _check_multi_member_availability(self, slot, availability_values):
        """Check if enough staff members are available for multi-member booking"""
        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
        available_staff = []
        
        for staff_user in self.staff_user_ids:
            if self._is_user_available_for_slot(staff_user, slot_start_dt_utc, slot_end_dt_utc, availability_values):
                available_staff.append(staff_user)
                

                if len(available_staff) >= (self.required_users_count or 1):

                    slot['available_staff_users'] = self.env['res.users'].browse([u.id for u in available_staff[:self.required_users_count]])
                    slot['staff_user_id'] = available_staff[0]  # Primary staff member
                    return True
        
        return False

    def _is_user_available_for_slot(self, staff_user, slot_start_dt_utc, slot_end_dt_utc, availability_values):
        """Check if a specific user is available for the given slot using Odoo's availability system"""

        temp_slot = {
            'UTC': [slot_start_dt_utc, slot_end_dt_utc],
            'slot': self.slot_ids[0] if self.slot_ids else None,
        }
        

        return self._slot_availability_is_user_available(temp_slot, staff_user, availability_values)
