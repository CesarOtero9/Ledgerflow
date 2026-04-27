document.addEventListener("DOMContentLoaded", function () {
    console.log("LedgerFlow visual engine iniciado.");

    const animatedElements = document.querySelectorAll(
        ".panel, .metric-card, .chart-panel, .module-header, .dashboard-hero, .extraction-card, .budget-health-card"
    );

    const observer = new IntersectionObserver(
        entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        },
        {
            threshold: 0.08
        }
    );

    animatedElements.forEach((element, index) => {
        element.classList.add("reveal-item");
        element.style.transitionDelay = `${Math.min(index * 45, 350)}ms`;
        observer.observe(element);
    });

    const menuLinks = document.querySelectorAll(".menu-link");
    const currentPath = window.location.pathname;

    menuLinks.forEach(link => {
        const href = link.getAttribute("href");

        if (!href || href === "#") {
            return;
        }

        if (currentPath === href || (href !== "/" && currentPath.startsWith(href))) {
            link.classList.add("active-menu-link");
        }
    });

    if (window.jQuery && $.fn.select2) {
        $(".select2-field").select2({
            width: "100%",
            allowClear: true,
            placeholder: "Selecciona una opción",
            language: {
                noResults: function () {
                    return "Sin resultados";
                }
            }
        });

        $(".select2-multiple").select2({
            width: "100%",
            placeholder: "Selecciona una o varias opciones",
            language: {
                noResults: function () {
                    return "Sin resultados";
                }
            }
        });
    }

    const appShell = document.getElementById("appShell");
    const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");

    function applySavedSidebarState() {
        const saved = localStorage.getItem("ledgerflow_sidebar_collapsed");
        if (saved === "true") {
            appShell.classList.add("sidebar-collapsed");
        }
    }

    function toggleSidebar() {
        appShell.classList.toggle("sidebar-collapsed");
        localStorage.setItem(
            "ledgerflow_sidebar_collapsed",
            appShell.classList.contains("sidebar-collapsed")
        );
    }

    applySavedSidebarState();

    if (sidebarToggleBtn) {
        sidebarToggleBtn.addEventListener("click", toggleSidebar);
    }
});