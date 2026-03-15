// OsteoAI - Main JS
document.addEventListener('DOMContentLoaded', function() {
  // Auto-dismiss alerts after 5 seconds
  setTimeout(function() {
    document.querySelectorAll('.alert').forEach(function(a) {
      a.style.transition = 'opacity .5s';
      a.style.opacity = '0';
      setTimeout(function() { a.remove(); }, 500);
    });
  }, 5000);

  // Highlight active nav link based on current path
  var path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(function(link) {
    if (link.getAttribute('href') === path) link.classList.add('active');
  });
});
