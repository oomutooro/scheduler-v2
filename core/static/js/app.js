/* Entebbe Airport Slotting System — App JavaScript */

// ── Theme initialization (runs as soon as this script loads) ──
(function() {
  try {
    const stored = localStorage.getItem('theme');
    if (stored === 'dark' ||
        (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('dark');
    }
  } catch (e) {
    // localStorage may be unavailable in some browsers
  }
})();

document.addEventListener('DOMContentLoaded', function () {
    // update icon based on current theme
    const updateIcon = () => {
      const icon = document.getElementById('theme-icon');
      if (!icon) return;
      if (document.documentElement.classList.contains('dark')) {
        icon.textContent = '☀';
      } else {
        icon.textContent = '🌙';
      }
    };

    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        document.documentElement.classList.toggle('dark');
        try {
          localStorage.theme = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
        } catch (_) {}
        updateIcon();
      });
      updateIcon();
    }

  // ── Auto-dismiss alerts after 5 seconds
  document.querySelectorAll('.alert').forEach(function (alert) {
    setTimeout(function () {
      alert.style.opacity = '0';
      alert.style.transition = 'opacity 0.4s';
      setTimeout(function () { alert.remove(); }, 400);
    }, 5000);
  });

  // ── Active nav highlighting (fallback via URL)
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(function (link) {
    const href = link.getAttribute('href');
    if (href && href !== '/' && path.startsWith(href)) {
      link.classList.add('active');
    }
  });

  // ── Day checkbox visual feedback
  document.querySelectorAll('.day-checkbox').forEach(function (label) {
    const cb = label.querySelector('input[type=checkbox]');
    if (!cb) return;
    function updateStyle() {
      if (cb.checked) {
        label.style.borderColor = 'var(--primary)';
        label.style.background = 'var(--primary-light)';
        const lbl = label.querySelector('.day-label');
        if (lbl) lbl.style.color = 'var(--primary)';
      } else {
        label.style.borderColor = '';
        label.style.background = '';
        const lbl = label.querySelector('.day-label');
        if (lbl) lbl.style.color = '';
      }
    }
    updateStyle();
    cb.addEventListener('change', updateStyle);
  });

  // ── Schedule table: highlight conflict rows
  document.querySelectorAll('.row-conflict').forEach(function (row) {
    row.title = 'This flight has a resource conflict';
  });

  // ── Dynamic flight form: show/hide fields based on operation type
  var opTypeSelect = document.getElementById('id_operation_type');
  if (opTypeSelect) {
    function toggleFlightFields() {
      var val = opTypeSelect.value;
      // Arrival number / time shown for: turnaround, arrival
      var arrivalGroup = document.getElementById('group_arrival_flight_number');
      var arrivalTimeGroup = document.getElementById('group_arrival_time');
      var departureGroup = document.getElementById('group_departure_flight_number');
      var departureTimeGroup = document.getElementById('group_departure_time');
      var originGroup = document.getElementById('group_origin');
      var destGroup = document.getElementById('group_destination');

      if (arrivalGroup)      arrivalGroup.style.display      = (val === 'departure') ? 'none' : '';
      if (arrivalTimeGroup)  arrivalTimeGroup.style.display  = (val === 'departure') ? 'none' : '';
      if (departureGroup)    departureGroup.style.display    = (val === 'arrival')   ? 'none' : '';
      if (departureTimeGroup) departureTimeGroup.style.display= (val === 'arrival')  ? 'none' : '';
      if (originGroup)       originGroup.style.display       = (val === 'departure') ? 'none' : '';
      if (destGroup)         destGroup.style.display         = (val === 'arrival')   ? 'none' : '';
    }
    opTypeSelect.addEventListener('change', toggleFlightFields);
    toggleFlightFields(); // run on page load
  }

  // ── Schedule page: auto-submit form when date changes
  var scheduleDateInput = document.getElementById('schedule_date_input');
  if (scheduleDateInput) {
    scheduleDateInput.addEventListener('change', function () {
      // Submit the parent form automatically
      var form = scheduleDateInput.closest('form');
      if (form) form.submit();
    });
  }

  // ── Allocations page: Select All / Deselect All checkbox
  var selectAllCb = document.getElementById('select_all_flights');
  if (selectAllCb) {
    selectAllCb.addEventListener('change', function () {
      document.querySelectorAll('.flight-select-cb').forEach(function (cb) {
        cb.checked = selectAllCb.checked;
      });
    });
    // Also update master checkbox state when individual boxes change
    document.querySelectorAll('.flight-select-cb').forEach(function (cb) {
      cb.addEventListener('change', function () {
        var all = document.querySelectorAll('.flight-select-cb');
        var checked = document.querySelectorAll('.flight-select-cb:checked');
        selectAllCb.checked = (all.length === checked.length);
        selectAllCb.indeterminate = (checked.length > 0 && checked.length < all.length);
      });
    });
  }

});
