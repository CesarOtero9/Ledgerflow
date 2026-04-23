document.addEventListener("DOMContentLoaded", function () {
    const dateInput = document.getElementById("application_date");
    const monthPreview = document.getElementById("month_preview");
    const amountInput = document.getElementById("amount");
    const categorySelect = document.getElementById("category_id");
    const subcategorySelect = document.getElementById("subcategory_id");

    const months = {
        1: "ENERO",
        2: "FEBRERO",
        3: "MARZO",
        4: "ABRIL",
        5: "MAYO",
        6: "JUNIO",
        7: "JULIO",
        8: "AGOSTO",
        9: "SEPTIEMBRE",
        10: "OCTUBRE",
        11: "NOVIEMBRE",
        12: "DICIEMBRE"
    };

    function initSelect2() {
        if (window.jQuery && $.fn.select2) {
            $(".select2-field").select2({
                width: "100%",
                placeholder: "Selecciona una opción",
                allowClear: true,
                language: {
                    noResults: function () {
                        return "Sin resultados";
                    },
                    searching: function () {
                        return "Buscando...";
                    }
                }
            });
        }
    }

    function updateMonthPreview() {
        const value = dateInput.value.trim();
        const parts = value.split("/");

        if (parts.length !== 3) {
            monthPreview.value = "";
            return;
        }

        const day = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10);
        const year = parseInt(parts[2], 10);

        if (!day || !month || !year || month < 1 || month > 12) {
            monthPreview.value = "";
            return;
        }

        monthPreview.value = months[month] || "";
    }

    function formatCurrencyInput() {
        let value = amountInput.value;

        value = value.replace("$", "").replaceAll(",", "").replace("MXN", "").trim();

        if (value === "") {
            amountInput.value = "";
            return;
        }

        const numberValue = Number(value);

        if (isNaN(numberValue)) {
            return;
        }

        amountInput.value = numberValue.toLocaleString("es-MX", {
            style: "currency",
            currency: "MXN"
        });
    }

    function loadSubcategories(categoryId, selectedSubcategoryId = "") {
        if (window.jQuery && $.fn.select2) {
            $("#subcategory_id").select2("destroy");
        }

        subcategorySelect.innerHTML = '<option value="">Sin subrubro</option>';

        if (!categoryId) {
            initSelect2();
            return;
        }

        fetch(`/registros/api/subrubros/${categoryId}`)
            .then(response => response.json())
            .then(data => {
                data.forEach(subcategory => {
                    const option = document.createElement("option");
                    option.value = subcategory.id;
                    option.textContent = subcategory.name;

                    if (String(subcategory.id) === String(selectedSubcategoryId)) {
                        option.selected = true;
                    }

                    subcategorySelect.appendChild(option);
                });

                initSelect2();
            })
            .catch(error => {
                console.error("Error al cargar subrubros:", error);
                initSelect2();
            });
    }

    initSelect2();

    if (dateInput) {
        dateInput.addEventListener("input", updateMonthPreview);
        updateMonthPreview();
    }

    if (amountInput) {
        amountInput.addEventListener("blur", formatCurrencyInput);
    }

    if (categorySelect) {
        $("#category_id").on("change", function () {
            loadSubcategories(this.value);
        });

        if (categorySelect.value && window.selectedSubcategoryId) {
            loadSubcategories(categorySelect.value, window.selectedSubcategoryId);
        }
    }
});