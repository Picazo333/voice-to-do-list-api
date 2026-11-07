(function () {
  var motion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function syncMotion() {
    document.documentElement.dataset.motion = motion.matches ? "reduced" : "full";
  }

  syncMotion();
  if (typeof motion.addEventListener === "function") {
    motion.addEventListener("change", syncMotion);
  } else if (typeof motion.addListener === "function") {
    motion.addListener(syncMotion);
  }

  var loading = document.getElementById("loading");
  var forms = document.querySelectorAll("form[data-flow]");
  var busy = false;

  forms.forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (busy) {
        event.preventDefault();
        return;
      }
      var field = form.querySelector("textarea");
      if (!field || !field.value.trim()) {
        return;
      }
      busy = true;
      if (loading) {
        loading.hidden = false;
      }
      var main = document.getElementById("contenido");
      if (main) {
        main.setAttribute("aria-busy", "true");
      }
      document.querySelectorAll("button[type='submit']").forEach(function (button) {
        button.disabled = true;
      });
    });
  });
})();
