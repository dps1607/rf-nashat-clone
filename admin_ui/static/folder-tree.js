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
  var libraryAssignments = {};  // folderId -> library name (e.g. 'rf_reference_library')
  var pendingSensitiveResolve = null;

  // ── Available libraries (v1: Drive loader only writes to rf_reference_library) ──
  var AVAILABLE_LIBRARIES = ['rf_reference_library'];
  var DEFAULT_LIBRARY = 'rf_reference_library';

  // ── DOM refs ───────────────────────────────────────────────────────
  var tree = document.getElementById('folder-tree');
  var modal = document.getElementById('sensitive-modal');
  var modalDriveName = document.getElementById('modal-drive-name');
  var modalCancel = document.getElementById('modal-cancel');
  var modalConfirm = document.getElementById('modal-confirm');
  var saveBtn = document.getElementById('btn-save');
  var refreshBtn = document.getElementById('btn-refresh');
  var toast = document.getElementById('save-toast');
  var pendingPanel = document.getElementById('pending-selections');
  var pendingList = document.getElementById('pending-list');
  var pendingCount = document.getElementById('pending-count');

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
      check.dataset.isFolder = '1';  // S3 bucketing — split at save time
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
      // Session 16 — file node with its own checkbox. v3 drive_loader
      // dispatches files by MIME, so file IDs are now valid selection
      // targets. Cascade semantics: folder checks propagate VISUAL
      // check state to contained files (for UX), but do NOT write to
      // selectionState. Files only land in selectionState when the user
      // explicitly checks them individually. This prevents a "check one
      // folder" click from producing N+1 Drive API calls at ingest time.
      var spacer = document.createElement('span');
      spacer.className = 'tree-toggle disabled';
      spacer.innerHTML = '&nbsp;';
      node.appendChild(spacer);

      var fileCheck = document.createElement('input');
      fileCheck.type = 'checkbox';
      fileCheck.className = 'tree-check file-check';
      fileCheck.dataset.id = item.id;
      fileCheck.dataset.name = item.name;
      fileCheck.dataset.isFolder = '0';  // S3 bucketing — split at save time
      node.appendChild(fileCheck);

      var fileIcon = document.createElement('span');
      fileIcon.className = 'file-icon';
      fileIcon.textContent = '\u00B7';
      fileIcon.setAttribute('aria-hidden', 'true');
      node.appendChild(fileIcon);

      var fname = document.createElement('span');
      fname.className = 'folder-name file-name';
      fname.textContent = item.name;
      node.appendChild(fname);

      wrapper.appendChild(node);

      // Individual-file selection handler: explicit toggles go to
      // selectionState directly. Parent-driven visual cascades are
      // handled by cascadeDown() and do NOT call this path.
      (function (chk) {
        chk.addEventListener('change', function (e) {
          e.stopPropagation();
          if (chk.checked) {
            selectionState[item.id] = true;
          } else {
            delete selectionState[item.id];
          }
          updateParentCheck(wrapper.parentElement);
        });
      })(fileCheck);
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
  // Session 16 — folder cascades propagate the VISUAL checked state to all
  // descendant checkboxes, but only FOLDER checkboxes write to
  // selectionState. File children light up as "included via parent" for
  // UX feedback without individually entering selectionState — otherwise
  // a single folder check would produce N+1 Drive API calls at ingest time.
  function cascadeDown(container, checked) {
    if (!container) return;
    var checks = container.querySelectorAll('.tree-check');
    for (var i = 0; i < checks.length; i++) {
      checks[i].checked = checked;
      checks[i].indeterminate = false;
      var id = checks[i].dataset.id;
      var isFolder = checks[i].dataset.isFolder === '1';
      if (id && isFolder) {
        if (checked) {
          selectionState[id] = true;
        } else {
          delete selectionState[id];
        }
      }
      // File children: visual state only, no selectionState mutation.
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

  // ── Pending Selections panel ───────────────────────────────────────
  function getFolderDisplayInfo(folderId) {
    // Find the tree node for this folder ID and pull its display name + ancestor path
    var node = tree.querySelector('.tree-node[data-id="' + folderId + '"]');
    if (!node) {
      // Fallback: it might be a drive-level checkbox
      var driveCheck = tree.querySelector('.drive-check[data-id="' + folderId + '"]');
      if (driveCheck) {
        var driveEl = driveCheck.closest('.tree-drive');
        var driveName = driveEl ? driveEl.querySelector('.drive-name').textContent.trim() : folderId;
        return { name: driveName, path: '(entire drive)' };
      }
      return { name: folderId, path: '' };
    }
    var nameEl = node.querySelector('.folder-name');
    var name = nameEl ? nameEl.textContent.trim() : folderId;
    // Build ancestor chain by walking up .tree-node-wrapper parents
    var path = [];
    var current = node.closest('.tree-node-wrapper');
    while (current) {
      var parentWrapper = current.parentElement && current.parentElement.closest('.tree-node-wrapper');
      if (parentWrapper) {
        var parentName = parentWrapper.querySelector(':scope > .tree-node > .folder-name');
        if (parentName) path.unshift(parentName.textContent.trim());
      } else {
        var driveEl2 = current.closest('.tree-drive');
        if (driveEl2) {
          var dn = driveEl2.querySelector('.drive-name');
          if (dn) path.unshift(dn.textContent.trim());
        }
        break;
      }
      current = parentWrapper;
    }
    return { name: name, path: path.join(' / ') };
  }

  function renderPendingSelections() {
    if (!pendingPanel || !pendingList || !pendingCount) return;
    var ids = Object.keys(selectionState);
    pendingCount.textContent = '(' + ids.length + ')';
    if (ids.length === 0) {
      pendingPanel.classList.add('hidden');
      pendingList.innerHTML = '';
      return;
    }
    pendingPanel.classList.remove('hidden');
    pendingList.innerHTML = '';
    for (var i = 0; i < ids.length; i++) {
      var fid = ids[i];
      // Default-assign to library if not already set
      if (!libraryAssignments[fid]) {
        libraryAssignments[fid] = DEFAULT_LIBRARY;
      }
      var info = getFolderDisplayInfo(fid);
      var row = document.createElement('div');
      row.className = 'pending-row';
      row.dataset.folderId = fid;

      var infoEl = document.createElement('div');
      infoEl.className = 'pending-row-info';
      var nameEl = document.createElement('span');
      nameEl.className = 'pending-row-name';
      nameEl.textContent = info.name;
      var pathEl = document.createElement('span');
      pathEl.className = 'pending-row-path';
      pathEl.textContent = info.path;
      infoEl.appendChild(nameEl);
      infoEl.appendChild(pathEl);
      row.appendChild(infoEl);

      var select = document.createElement('select');
      select.className = 'pending-row-library';
      select.dataset.folderId = fid;
      for (var j = 0; j < AVAILABLE_LIBRARIES.length; j++) {
        var opt = document.createElement('option');
        opt.value = AVAILABLE_LIBRARIES[j];
        opt.textContent = AVAILABLE_LIBRARIES[j];
        if (AVAILABLE_LIBRARIES[j] === libraryAssignments[fid]) opt.selected = true;
        select.appendChild(opt);
      }
      (function (sel, fid2) {
        sel.addEventListener('change', function () {
          libraryAssignments[fid2] = sel.value;
        });
      })(select, fid);
      row.appendChild(select);

      var rm = document.createElement('button');
      rm.type = 'button';
      rm.className = 'pending-row-remove';
      rm.title = 'Remove from selection';
      rm.textContent = '×';
      (function (fid3) {
        rm.addEventListener('click', function () {
          // Uncheck the corresponding checkbox in the tree (fires its change handler, which updates selectionState + parents)
          var chk = tree.querySelector('.tree-check[data-id="' + fid3 + '"]');
          if (chk && chk.checked) {
            chk.checked = false;
            // Manually mirror the change handler effects:
            delete selectionState[fid3];
            delete libraryAssignments[fid3];
            // Also cascade & update parents
            var wrapper = chk.closest('.tree-node-wrapper');
            var driveEl3 = chk.closest('.tree-drive');
            var childContainer = wrapper
              ? wrapper.querySelector(':scope > .tree-children')
              : (driveEl3 ? driveEl3.querySelector('.tree-children') : null);
            if (childContainer) cascadeDown(childContainer, false);
            updateParentCheck(wrapper ? wrapper.parentElement : (driveEl3 ? driveEl3 : null));
          } else {
            // Already unchecked somehow — just clean up state
            delete selectionState[fid3];
            delete libraryAssignments[fid3];
          }
          renderPendingSelections();
        });
      })(fid);
      row.appendChild(rm);

      pendingList.appendChild(row);
    }
    // Garbage-collect library_assignments entries for folders no longer selected
    var validKeys = {};
    for (var k = 0; k < ids.length; k++) validKeys[ids[k]] = true;
    for (var key in libraryAssignments) {
      if (!validKeys[key]) delete libraryAssignments[key];
    }
  }

  // Hook the pending-panel re-render into checkbox cascades.
  // We wrap cascadeDown and updateParentCheck so any path that mutates
  // selectionState triggers a re-render, without having to touch every
  // event handler individually.
  var _origCascade = cascadeDown;
  cascadeDown = function (container, checked) {
    _origCascade(container, checked);
    renderPendingSelections();
  };
  var _origUpdateParent = updateParentCheck;
  updateParentCheck = function (container) {
    _origUpdateParent(container);
    renderPendingSelections();
  };

  // ── Save ───────────────────────────────────────────────────────────
  if (saveBtn) {
    saveBtn.addEventListener('click', function () {
      // Session 16 — read selection from the DOM, not from selectionState.
      // The DOM is the source of truth (that's what the user sees). The
      // selectionState JS object is a cache that historically can drift
      // out of sync — for example, drive-level checkbox change handlers
      // never wrote to it, so checking a drive root produced a "Nothing
      // selected" save error even though the visible checkbox was on.
      // By reading directly from `:checked` selectors at save time, we
      // guarantee the save matches what the user sees.
      var selectedFolders = [];
      var selectedFiles = [];
      var driveRootIds = [];

      // Drive-root checkboxes: ids are drive_ids, not folder_ids. v3 doesn't
      // currently support drive-root selection (BACKLOG #22). Surface a clear
      // message rather than letting them fall through into selected_folders
      // where the manifest validation would reject them with confusing copy.
      var driveChecks = document.querySelectorAll('.drive-check:checked');
      for (var di = 0; di < driveChecks.length; di++) {
        var did = driveChecks[di].dataset.id;
        if (did) driveRootIds.push(did);
      }

      // Folder + file checkboxes: split by data-is-folder dataset tag.
      var folderFileChecks = document.querySelectorAll('.tree-check:checked:not(.drive-check)');
      for (var fi = 0; fi < folderFileChecks.length; fi++) {
        var chk = folderFileChecks[fi];
        var fid = chk.dataset.id;
        if (!fid) continue;
        if (chk.dataset.isFolder === '0') {
          selectedFiles.push(fid);
        } else {
          selectedFolders.push(fid);
        }
      }

      var totalCount = selectedFolders.length + selectedFiles.length;
      if (totalCount === 0 && driveRootIds.length === 0) {
        showToast('Nothing selected', 'error');
        return;
      }
      if (totalCount === 0 && driveRootIds.length > 0) {
        showToast('Selecting whole drives is not supported yet — expand the drive and select individual folders', 'error');
        return;
      }

      // Build library_assignments. Default to rf_reference_library for
      // any selection that doesn't have an explicit assignment in the
      // pending panel (handles the case where a folder was checked but
      // the panel-render hasn't run yet, or selectionState got out of sync).
      var assignments = {};
      var allSelected = selectedFolders.concat(selectedFiles);
      for (var i = 0; i < allSelected.length; i++) {
        var sid = allSelected[i];
        var lib = libraryAssignments[sid];
        assignments[sid] = (lib && AVAILABLE_LIBRARIES.indexOf(lib) !== -1)
          ? lib
          : DEFAULT_LIBRARY;
      }

      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';

      fetch('/admin/api/folders/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selected_folders: selectedFolders,
          selected_files: selectedFiles,
          library_assignments: assignments,
          timestamp: new Date().toISOString(),
        }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save Selection';
          if (data.ok) {
            var parts = [];
            if (data.saved_folders) parts.push(data.saved_folders + ' folder' + (data.saved_folders !== 1 ? 's' : ''));
            if (data.saved_files) parts.push(data.saved_files + ' file' + (data.saved_files !== 1 ? 's' : ''));
            showToast('Saved ' + parts.join(' + '), 'success');
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
