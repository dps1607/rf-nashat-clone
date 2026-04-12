/**
 * Folder tree component — Phase D-post
 *
 * Handles: drive expand/collapse with 2-level prefetch, deeper lazy loading,
 * flat-drive rendering (8-labs), checkbox cascade (tri-state),
 * sensitive-drive modal, save, and inventory refresh.
 */
(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────────────
  var selectionState = {};  // folderId -> true (checked)
  var pendingSensitiveResolve = null;

  // ── DOM refs ───────────────────────────────────────────────────────
  var tree = document.getElementById('folder-tree');
  var modal = document.getElementById('sensitive-modal');
  var modalDriveName = document.getElementById('modal-drive-name');
  var modalCancel = document.getElementById('modal-cancel');
  var modalConfirm = document.getElementById('modal-confirm');
  var saveBtn = document.getElementById('btn-save');
  var refreshBtn = document.getElementById('btn-refresh');
  var toast = document.getElementById('save-toast');

  // ── Init ───────────────────────────────────────────────────────────
  if (tree) {
    var driveEls = tree.querySelectorAll('.tree-drive');
    for (var i = 0; i < driveEls.length; i++) {
      initDriveNode(driveEls[i]);
    }
  }

  // ── Drive node setup ───────────────────────────────────────────────
  function initDriveNode(driveEl) {
    var toggle = driveEl.querySelector('.tree-toggle');
    var check = driveEl.querySelector('.tree-check');
    var childContainer = driveEl.querySelector('.tree-children');
    var driveId = driveEl.dataset.driveId;
    var slug = driveEl.dataset.slug;
    var sensitive = driveEl.dataset.sensitive === 'true';
    var totalFolders = parseInt(driveEl.dataset.totalFolders, 10) || 0;
    var totalFiles = parseInt(driveEl.dataset.totalFiles, 10) || 0;

    if (!driveId) return;  // not_shared

    // Expand/collapse
    toggle.addEventListener('click', function () {
      if (childContainer.dataset.loaded === 'false') {
        loadDriveTree(toggle, childContainer, driveId, slug, sensitive, totalFolders, totalFiles);
      } else {
        toggleVisibility(toggle, childContainer);
      }
    });

    // Keyboard support
    toggle.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggle.click();
      }
    });

    // Checkbox
    check.addEventListener('change', function () {
      if (sensitive && check.checked) {
        check.checked = false;
        showSensitiveModal(driveEl.querySelector('.drive-name').textContent.trim())
          .then(function (confirmed) {
            if (confirmed) {
              check.checked = true;
              cascadeDown(childContainer, true);
            }
          });
        return;
      }
      cascadeDown(childContainer, check.checked);
    });
  }

  // ── Load drive tree (2-level prefetch) ─────────────────────────────
  function loadDriveTree(toggle, container, driveId, slug, sensitive, totalFolders, totalFiles) {
    toggle.textContent = '\u25CB';  // loading indicator
    toggle.classList.add('loading');

    fetch('/admin/api/drive/' + encodeURIComponent(driveId) + '/tree?slug=' + encodeURIComponent(slug))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        toggle.classList.remove('loading');
        container.innerHTML = '';

        var children = data.children || [];
        var rootFileCount = data.root_file_count || 0;

        // Flat drive case (e.g. 8-labs: 0 folders, files at root)
        if (children.length === 0 && rootFileCount > 0) {
          var msg = document.createElement('div');
          msg.className = 'flat-drive-msg';
          msg.textContent = rootFileCount + ' file' + (rootFileCount !== 1 ? 's' : '') + ' at drive root (no subfolders)';
          container.appendChild(msg);
        } else {
          renderChildren(container, children, driveId, sensitive, 1);
        }

        container.dataset.loaded = 'true';
        container.classList.remove('hidden');
        toggle.textContent = '\u25BC';
        toggle.classList.add('expanded');
      })
      .catch(function (err) {
        toggle.classList.remove('loading');
        toggle.textContent = '\u25B6';
        showToast('Failed to load drive tree: ' + err.message, 'error');
      });
  }

  // ── Render children into container ─────────────────────────────────
  function renderChildren(container, children, driveId, sensitive, depth) {
    for (var i = 0; i < children.length; i++) {
      var item = children[i];
      var nodeEl = createTreeNode(item, driveId, sensitive, depth);
      container.appendChild(nodeEl);

      // If this folder has pre-fetched children (2-level prefetch), render them
      if (item.is_folder && item.children && item.children.length > 0) {
        var subContainer = nodeEl.querySelector('.tree-children');
        if (subContainer) {
          renderChildren(subContainer, item.children, driveId, sensitive, depth + 1);
          subContainer.dataset.loaded = 'true';
        }
      }
    }
  }

  // ── Create a single tree node element ──────────────────────────────
  function createTreeNode(item, driveId, sensitive, depth) {
    var wrapper = document.createElement('div');
    wrapper.className = 'tree-node-wrapper';

    var node = document.createElement('div');
    node.className = 'tree-node' + (item.is_folder ? '' : ' file-node');
    node.style.paddingLeft = (depth * 1.25 + 0.75) + 'rem';
    node.dataset.id = item.id;
    node.dataset.driveId = driveId;

    if (item.is_folder) {
      // Toggle arrow
      var toggle = document.createElement('span');
      toggle.className = 'tree-toggle expandable';
      toggle.textContent = '\u25B6';
      toggle.setAttribute('role', 'button');
      toggle.setAttribute('tabindex', '0');
      node.appendChild(toggle);

      // Checkbox
      var check = document.createElement('input');
      check.type = 'checkbox';
      check.className = 'tree-check';
      check.dataset.id = item.id;
      node.appendChild(check);

      // Name
      var name = document.createElement('span');
      name.className = 'folder-name';
      name.textContent = item.name;
      node.appendChild(name);

      // File count badge
      var fc = item.file_count_direct || 0;
      if (fc > 0) {
        var badge = document.createElement('span');
        badge.className = 'folder-file-count';
        badge.textContent = fc + ' file' + (fc !== 1 ? 's' : '');
        node.appendChild(badge);
      }

      wrapper.appendChild(node);

      // Children container
      var childContainer = document.createElement('div');
      childContainer.className = 'tree-children hidden';
      childContainer.dataset.loaded = 'false';
      wrapper.appendChild(childContainer);

      // Toggle handler
      (function (tog, cc, itemId) {
        tog.addEventListener('click', function () {
          if (cc.dataset.loaded === 'false') {
            loadFolderChildren(tog, cc, itemId, driveId, sensitive, depth + 1);
          } else {
            toggleVisibility(tog, cc);
          }
        });
        tog.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            tog.click();
          }
        });
      })(toggle, childContainer, item.id);

      // Checkbox handler
      (function (chk, cc) {
        chk.addEventListener('change', function () {
          if (sensitive && chk.checked) {
            chk.checked = false;
            showSensitiveModal(item.name)
              .then(function (confirmed) {
                if (confirmed) {
                  chk.checked = true;
                  selectionState[item.id] = true;
                  cascadeDown(cc, true);
                  updateParentCheck(wrapper.parentElement);
                }
              });
            return;
          }
          if (chk.checked) {
            selectionState[item.id] = true;
          } else {
            delete selectionState[item.id];
          }
          cascadeDown(cc, chk.checked);
          updateParentCheck(wrapper.parentElement);
        });
      })(check, childContainer);

    } else {
      // File node — no toggle, just a checkbox and name
      var spacer = document.createElement('span');
      spacer.className = 'tree-toggle disabled';
      spacer.innerHTML = '&nbsp;';
      node.appendChild(spacer);

      var fcheck = document.createElement('input');
      fcheck.type = 'checkbox';
      fcheck.className = 'tree-check';
      fcheck.dataset.id = item.id;
      node.appendChild(fcheck);

      var fname = document.createElement('span');
      fname.className = 'folder-name';
      fname.textContent = item.name;
      node.appendChild(fname);

      wrapper.appendChild(node);

      // File checkbox handler
      (function (chk) {
        chk.addEventListener('change', function () {
          if (chk.checked) {
            selectionState[item.id] = true;
          } else {
            delete selectionState[item.id];
          }
          updateParentCheck(wrapper.parentElement);
        });
      })(fcheck);
    }

    return wrapper;
  }

  // ── Lazy-load folder children (depth 2+) ───────────────────────────
  function loadFolderChildren(toggle, container, folderId, driveId, sensitive, depth) {
    toggle.textContent = '\u25CB';
    toggle.classList.add('loading');

    fetch('/admin/api/folder/' + encodeURIComponent(folderId) + '/children?drive_id=' + encodeURIComponent(driveId))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        toggle.classList.remove('loading');
        container.innerHTML = '';
        var children = data.children || [];
        if (children.length === 0) {
          var empty = document.createElement('div');
          empty.className = 'flat-drive-msg';
          empty.textContent = 'Empty folder';
          container.appendChild(empty);
        } else {
          renderChildren(container, children, driveId, sensitive, depth);
        }
        container.dataset.loaded = 'true';
        container.classList.remove('hidden');
        toggle.textContent = '\u25BC';
        toggle.classList.add('expanded');
      })
      .catch(function (err) {
        toggle.classList.remove('loading');
        toggle.textContent = '\u25B6';
        showToast('Failed to load folder: ' + err.message, 'error');
      });
  }

  // ── Toggle visibility ──────────────────────────────────────────────
  function toggleVisibility(toggle, container) {
    var isHidden = container.classList.toggle('hidden');
    if (isHidden) {
      toggle.textContent = '\u25B6';
      toggle.classList.remove('expanded');
    } else {
      toggle.textContent = '\u25BC';
      toggle.classList.add('expanded');
    }
  }

  // ── Cascade checkbox state down ────────────────────────────────────
  function cascadeDown(container, checked) {
    if (!container) return;
    var checks = container.querySelectorAll('.tree-check');
    for (var i = 0; i < checks.length; i++) {
      checks[i].checked = checked;
      checks[i].indeterminate = false;
      var id = checks[i].dataset.id;
      if (id) {
        if (checked) {
          selectionState[id] = true;
        } else {
          delete selectionState[id];
        }
      }
    }
  }

  // ── Update parent checkbox to reflect child state ──────────────────
  function updateParentCheck(container) {
    if (!container) return;
    // Walk up to find the parent node wrapper
    var parentWrapper = container.closest('.tree-node-wrapper');
    if (!parentWrapper) {
      // Might be at drive level
      var driveEl = container.closest('.tree-drive');
      if (driveEl) {
        updateDriveCheck(driveEl);
      }
      return;
    }

    var parentCheck = parentWrapper.querySelector(':scope > .tree-node > .tree-check');
    if (!parentCheck) return;

    var childContainer = parentWrapper.querySelector(':scope > .tree-children');
    if (!childContainer) return;

    var childChecks = childContainer.querySelectorAll('.tree-check');
    if (childChecks.length === 0) return;

    var checkedCount = 0;
    for (var i = 0; i < childChecks.length; i++) {
      if (childChecks[i].checked) checkedCount++;
    }

    if (checkedCount === 0) {
      parentCheck.checked = false;
      parentCheck.indeterminate = false;
      delete selectionState[parentCheck.dataset.id];
    } else if (checkedCount === childChecks.length) {
      parentCheck.checked = true;
      parentCheck.indeterminate = false;
      selectionState[parentCheck.dataset.id] = true;
    } else {
      parentCheck.checked = false;
      parentCheck.indeterminate = true;
      delete selectionState[parentCheck.dataset.id];
    }

    // Continue up
    var grandparent = parentWrapper.parentElement;
    if (grandparent) {
      updateParentCheck(grandparent);
    }
  }

  function updateDriveCheck(driveEl) {
    var driveCheck = driveEl.querySelector('.drive-check');
    var childContainer = driveEl.querySelector('.tree-children');
    if (!driveCheck || !childContainer) return;

    var childChecks = childContainer.querySelectorAll('.tree-check');
    if (childChecks.length === 0) return;

    var checkedCount = 0;
    for (var i = 0; i < childChecks.length; i++) {
      if (childChecks[i].checked) checkedCount++;
    }

    if (checkedCount === 0) {
      driveCheck.checked = false;
      driveCheck.indeterminate = false;
    } else if (checkedCount === childChecks.length) {
      driveCheck.checked = true;
      driveCheck.indeterminate = false;
    } else {
      driveCheck.checked = false;
      driveCheck.indeterminate = true;
    }
  }

  // ── Sensitive drive modal ──────────────────────────────────────────
  function showSensitiveModal(driveName) {
    return new Promise(function (resolve) {
      modalDriveName.textContent = driveName;
      modal.classList.remove('hidden');
      pendingSensitiveResolve = resolve;
    });
  }

  if (modalCancel) {
    modalCancel.addEventListener('click', function () {
      modal.classList.add('hidden');
      if (pendingSensitiveResolve) {
        pendingSensitiveResolve(false);
        pendingSensitiveResolve = null;
      }
    });
  }

  if (modalConfirm) {
    modalConfirm.addEventListener('click', function () {
      modal.classList.add('hidden');
      if (pendingSensitiveResolve) {
        pendingSensitiveResolve(true);
        pendingSensitiveResolve = null;
      }
    });
  }

  // Close modal on backdrop click
  if (modal) {
    modal.querySelector('.modal-backdrop').addEventListener('click', function () {
      modal.classList.add('hidden');
      if (pendingSensitiveResolve) {
        pendingSensitiveResolve(false);
        pendingSensitiveResolve = null;
      }
    });
  }

  // ── Save ───────────────────────────────────────────────────────────
  if (saveBtn) {
    saveBtn.addEventListener('click', function () {
      var selectedFolders = Object.keys(selectionState);
      if (selectedFolders.length === 0) {
        showToast('No folders selected', 'error');
        return;
      }

      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';

      fetch('/admin/api/folders/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selected_folders: selectedFolders,
          library_assignments: {},
          timestamp: new Date().toISOString(),
        }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save Selection';
          if (data.ok) {
            showToast('Saved ' + data.saved_folders + ' folder selections', 'success');
          } else {
            showToast('Save failed: ' + (data.error || 'unknown'), 'error');
          }
        })
        .catch(function (err) {
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save Selection';
          showToast('Save error: ' + err.message, 'error');
        });
    });
  }

  // ── Refresh inventory ──────────────────────────────────────────────
  if (refreshBtn) {
    refreshBtn.addEventListener('click', function () {
      refreshBtn.disabled = true;
      refreshBtn.textContent = 'Refreshing...';

      fetch('/admin/api/folders/refresh-inventory', { method: 'POST' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          refreshBtn.disabled = false;
          refreshBtn.textContent = 'Refresh Inventory';
          if (data.ok) {
            showToast('Inventory refreshed (' + data.drives + ' drives)', 'success');
            setTimeout(function () { window.location.reload(); }, 1000);
          } else {
            showToast('Refresh failed — no manifest found', 'error');
          }
        })
        .catch(function (err) {
          refreshBtn.disabled = false;
          refreshBtn.textContent = 'Refresh Inventory';
          showToast('Refresh error: ' + err.message, 'error');
        });
    });
  }

  // ── Toast ──────────────────────────────────────────────────────────
  function showToast(message, type) {
    if (!toast) return;
    toast.textContent = message;
    toast.className = 'toast toast-' + (type || 'info');
    // Force reflow for re-animation
    void toast.offsetWidth;
    setTimeout(function () {
      toast.classList.add('hidden');
    }, 3000);
  }

  // ── Public API (for search component) ──────────────────────────────
  window.FolderTree = {
    expandToFolder: function (driveSlug, folderId) {
      // Find and expand the drive
      var driveEl = tree.querySelector('[data-slug="' + driveSlug + '"]');
      if (!driveEl) return;

      var toggle = driveEl.querySelector('.tree-toggle');
      var childContainer = driveEl.querySelector('.tree-children');

      if (childContainer.dataset.loaded === 'false') {
        // Need to load first, then find the node
        toggle.click();
        // After load, try to highlight
        setTimeout(function () {
          highlightNode(folderId);
        }, 1000);
      } else {
        if (childContainer.classList.contains('hidden')) {
          toggle.click();
        }
        highlightNode(folderId);
      }
    }
  };

  function highlightNode(folderId) {
    // Find node by data-id
    var node = tree.querySelector('.tree-node[data-id="' + folderId + '"]');
    if (node) {
      node.classList.add('highlighted');
      node.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(function () {
        node.classList.remove('highlighted');
      }, 2000);
    }
  }

})();
