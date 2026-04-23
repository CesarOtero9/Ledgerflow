document.addEventListener("DOMContentLoaded", function () {
    console.log("LedgerFlow visual engine iniciado.");

    const animatedElements = document.querySelectorAll(
        ".panel, .metric-card, .chart-panel, .module-header, .dashboard-hero, .extraction-card"
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

        if (currentPath === href || currentPath.startsWith(href)) {
            link.classList.add("active-menu-link");
        }
    });
});