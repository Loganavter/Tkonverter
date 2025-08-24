import logging
from typing import Optional, Set

from PyQt6.QtCore import QObject, pyqtSignal

from core.analysis.tree_analyzer import TreeNode

logger = logging.getLogger(__name__)

class AnalysisPresenter(QObject):

    filter_changed = pyqtSignal(set)

    def __init__(self):
        super().__init__()
        self.view = None

    def get_view(self, parent):

        from ui.dialogs.analysis.analysis_dialog import AnalysisDialog
        from ui.theme import ThemeManager

        if self.view is None:
            self.view = AnalysisDialog(
                presenter=self,
                theme_manager=ThemeManager.get_instance(),
                parent=parent,
            )

            self.view.rejected.connect(self.on_view_closed)
            self.view.finished.connect(self.on_view_closed)
        return self.view

    def load_analysis_data(self, root_node: TreeNode, initial_disabled_nodes: Set[TreeNode], unit: str):
        if self.view:
            self.view.load_data_and_show(root_node, initial_disabled_nodes, unit)
        else:
            logger.error("[AnalysisPresenter] view is None, cannot load data")

    def on_filter_accepted(self, new_disabled_nodes: set):
        self.filter_changed.emit(new_disabled_nodes)

    def on_view_closed(self):

        self.view = None

