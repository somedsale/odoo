// Add resize handle to search panel
(function () {
    const STORAGE_KEY_PREFIX = 'sidebar_width_';
    let isResizing = false;
    let currentPanel = null;
    let startX = 0;
    let startWidth = 0;

    function getStorageKey(panel) {
        return STORAGE_KEY_PREFIX + (panel.id || panel.className);
    }

    function restorePanelWidth(panel) {
        const storageKey = getStorageKey(panel);
        const savedWidth = localStorage.getItem(storageKey);
        if (savedWidth) {
            panel.style.width = savedWidth;
        }
    }

    function savePanelWidth(panel) {
        const storageKey = getStorageKey(panel);
        localStorage.setItem(storageKey, panel.style.width);
    }

    function updatePanelOverflowState(panel) {
        panel.classList.toggle('has-scrollbar', panel.scrollHeight > panel.clientHeight);
    }

    function addResizeHandles() {
        const panels = document.querySelectorAll(".o_search_panel:not([data-resize-handle='added']), .o-mail-DiscussSidebar:not([data-resize-handle='added'])");

        panels.forEach((panel) => {
            if (panel.querySelector(".o_resize_handle")) {
                panel.setAttribute("data-resize-handle", "added");
                return;
            }

            const handle = document.createElement("div");
            handle.className = "o_resize_handle";
            handle.setAttribute("title", "Kéo để thay đổi kích thước thanh bên");
            handle.setAttribute("aria-label", "Resize sidebar");
            handle.innerHTML = '';

            // Drag event handlers
            handle.addEventListener('mousedown', onMouseDown);
            panel.addEventListener('scroll', () => updatePanelOverflowState(panel));

            if (window.ResizeObserver) {
                const resizeObserver = new ResizeObserver(() => updatePanelOverflowState(panel));
                resizeObserver.observe(panel);
            }

            panel.style.resize = 'none';
            panel.style.position = 'relative';
            panel.insertBefore(handle, panel.firstChild);
            panel.setAttribute("data-resize-handle", "added");

            // Restore saved width and overflow state
            restorePanelWidth(panel);
            updatePanelOverflowState(panel);
        });
    }

    function onMouseDown(e) {
        isResizing = true;
        currentPanel = e.target.closest('.o_search_panel, .o-mail-DiscussSidebar');
        startX = e.clientX;
        startWidth = currentPanel.offsetWidth;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    }

    document.addEventListener('mousemove', (e) => {
        if (!isResizing || !currentPanel) return;

        const diff = e.clientX - startX;
        const newWidth = startWidth + diff;

        // Set minimum width (300px)
        if (newWidth > 300) {
            currentPanel.style.width = newWidth + 'px';
        }
    });

    document.addEventListener('mouseup', () => {
        if (isResizing && currentPanel) {
            isResizing = false;
            savePanelWidth(currentPanel);
            document.body.style.cursor = 'auto';
            document.body.style.userSelect = 'auto';
            currentPanel = null;
        }
    });

    function initObserver() {
        if (document.body) {
            // Watch for dynamic changes
            const observer = new MutationObserver(addResizeHandles);
            observer.observe(document.body, { childList: true, subtree: true });
        }
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener("DOMContentLoaded", function () {
            addResizeHandles();
            initObserver();
        });
    } else {
        addResizeHandles();
        initObserver();
    }
})();


