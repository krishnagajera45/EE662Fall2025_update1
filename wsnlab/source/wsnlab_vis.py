"""Visualisation of wsnlab library. Based on wsnsimpy_tk. Used package instead of message by Mustafa Tosun.
"""
from source import wsnlab
from source.wsnlab import *
from threading import Thread
from topovis import Scene
from topovis.TkPlotter import Plotter
import os

# Import for snapshot visualization
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend for PNG generation
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from PIL import ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def _ensure_snapshot_folder(config_module):
    """Ensure the snapshot folder exists and return its path.
    
    Args:
        config_module: Config module with SNAPSHOT_FOLDER setting
    
    Returns:
        str: Path to the snapshot folder
    """
    folder_name = getattr(config_module, 'SNAPSHOT_FOLDER', 'snapshots')
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    return folder_name


class Node(wsnlab.Node):
    """Class to model a visualised network node inherited wsnlab.Node.

       Attributes:
           scene (Scene): Scene object to visualise

    """

    ###################
    def __init__(self, sim, id, pos):
        """Constructor for visualised Node class. Creates a node in topovis scene.

           Args:
               sim (Simulator): Simulation environment of node.
               id (int): Global unique ID of node.
               pos (Tuple(double,double)): Position of node.

           Returns:
               Node: Created node object.
        """
        super().__init__(sim, id, pos)
        self.scene = self.sim.scene
        self.scene.node(id, *pos)

    ###################
    def send(self, pck):
        """Visualise sending process in addition to base send method.

           Args:
               pck (Dict): Package to be sent.

           Returns:

        """
        # UNcomment for Radio Circles 

        #obj_id = self.scene.circle(
        #    self.pos[0], self.pos[1],
        #    self.tx_range,
        #    line="wsnsimpy:tx")
        
        super().send(pck)
        
        #Uncomment for Radio Circles 
        #self.delayed_exec(0.2, self.scene.delshape, obj_id)
        
        # When unicast is added, it needs to be re-arranged
        # if not pck['dest'].is_equal(wsnlab.BROADCAST_ADDR):
        #     destPos = self.sim.nodes[pck['dest'].l].pos
        #     obj_id = self.scene.line(
        #         self.pos[0], self.pos[1],
        #         destPos[0], destPos[1],
        #         line="wsnsimpy:unicast")
        #     self.delayed_exec(0.2,self.scene.delshape,obj_id)

    ###################


    def draw_tx_range(self):
        """Draws transmission range of the node.

           Args:

           Returns:

        """
        # Store circle ID for later deletion (e.g., when becoming router)
        obj_id = self.scene.circle(self.pos[0], self.pos[1], self.tx_range, line="wsnsimpy:tx")
        self.tx_range_circle_id = obj_id
        #self.delayed_exec(0.2, self.scene.delshape, obj_id)



    def move(self, x, y):
        """Visualise move process in addition to base move method.

           Args:
               x (double): x of position.
               y (double): y of position.

           Returns:

        """
        super().move(x, y)
        self.scene.nodemove(self.id, x, y)

    ####################
    def draw_parent(self):
        """Draws parent relation to given destination address.

           Args:

           Returns:

        """
        self.scene.addlink(self.parent_gui, self.id, "parent")

    ####################
    def erase_parent(self):
        """Draws parent relation to given destination address.

           Args:

           Returns:

        """
        if self.parent_gui is not None:
            self.scene.dellink(self.parent_gui, self.id, "parent")


###########################################################
class _FakeScene:
    def _fake_method(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return self._fake_method


###########################################################


###########################################################
class Simulator(wsnlab.Simulator):
    '''Wrap WsnSimPy's Simulator class so that Tk main loop can be started in the
    main thread

    Attributes:
        visual (bool): A flag to visualising process.
        terrain_size (Tuple(double,double)): Size of visualised terrain.
    '''

    def __init__(self, duration, timescale=1, seed=0, terrain_size=(1000, 1000), visual=True, title=None):
        """Constructor for visualised Simulator class.

           Args:
               duration (double): Duration of simulation.
               timescale (double): Seconds in real time for 1 second in simulation. It arranges speed of simulation
               seed (double): seed for Random bbject.
               terrain_size (Tuple(double,double)): Size of visualised terrain.
               visual (bool): A flag to visualising process.
               title (string): Title of scene.

           Returns:
               Simulator: Created Simulator object.
        """
        super().__init__(duration, timescale, seed)
        self.visual = visual
        self.terrain_size = terrain_size
        if self.visual:
            self.scene = Scene(realtime=True)
            self.scene.linestyle("wsnsimpy:tx", color=(0, 0, 1), dash=(5, 5))
            self.scene.linestyle("wsnsimpy:ack", color=(0, 1, 1), dash=(5, 5))
            self.scene.linestyle("wsnsimpy:unicast", color=(0, 0, 1), width=3, arrow='head')
            self.scene.linestyle("wsnsimpy:collision", color=(1, 0, 0), width=3)
            self.scene.linestyle("parent", color=(0,.8,0), arrow="tail", width=2)
            if title is None:
                title = "WsnSimPy"
            self.tkplot = Plotter(windowTitle=title, terrain_size=terrain_size)
            self.tk = self.tkplot.tk
            self.scene.addPlotter(self.tkplot)
            self.scene.init(*terrain_size)
            
            # Set background color from config (delayed to ensure window is ready)
            try:
                from source import config
                bg_color = getattr(config, 'SIM_BACKGROUND_COLOR', 'lightgray')
                # Use after_idle to set background once window is fully initialized
                self.tk.after_idle(lambda: self._set_canvas_background(bg_color))
                # Set time text color based on background (black for white, white for dark)
                self.tk.after_idle(lambda: self._set_time_text_color(bg_color))
            except Exception:
                pass  # If config not available, use default
        else:
            self.scene = _FakeScene()

    def _set_canvas_background(self, bg_color):
        """Set the background color of the simulation canvas.
        
        Args:
            bg_color (str): Background color (e.g., 'white', 'lightgray', '#FFFFFF')
        """
        try:
            # Method 1: Try to access canvas through plotter
            if hasattr(self.tkplot, 'canvas'):
                self.tkplot.canvas.config(bg=bg_color)
                return
            
            # Method 2: Try to find canvas widget in the Tkinter window
            root = self.tk
            canvas = None
            
            # Search for canvas widget recursively
            def find_canvas(widget):
                if 'canvas' in str(widget).lower() or 'Canvas' in str(type(widget)):
                    return widget
                for child in widget.winfo_children():
                    result = find_canvas(child)
                    if result:
                        return result
                return None
            
            canvas = find_canvas(root)
            
            if canvas:
                canvas.config(bg=bg_color)
            else:
                # Method 3: If canvas not found, try setting root window background
                root.config(bg=bg_color)
        except Exception as e:
            # Silently fail if we can't set background color
            pass

    def _set_time_text_color(self, bg_color):
        """Set the time text color based on background color for visibility.
        
        Args:
            bg_color (str): Background color (e.g., 'white', 'lightgray', '#FFFFFF')
        """
        try:
            # Determine text color based on background
            bg_lower = bg_color.lower()
            if bg_lower in ['white', '#ffffff', '#fff', 'w']:
                text_color = 'black'
            elif bg_lower in ['lightgray', 'light grey', '#d3d3d3', '#f0f0f0']:
                text_color = 'black'
            else:
                # For dark backgrounds, use white text
                text_color = 'white'
            
            # Set time text color if plotter has timeText
            if hasattr(self.tkplot, 'timeText') and hasattr(self.tkplot, 'canvas'):
                try:
                    self.tkplot.canvas.itemconfigure(self.tkplot.timeText, fill=text_color)
                except Exception:
                    pass
        except Exception as e:
            # Silently fail if we can't set text color
            pass

    def _update_time(self):
        """Updates time in scene.

           Args:

           Returns:
        """
        while True:
            try:
                self.scene.setTime(self.now)
            except Exception as e:
                # GUI window was closed - stop updating time
                # This is harmless, simulation continues without visualization
                if "invalid command name" in str(e) or "TclError" in str(type(e).__name__):
                    break  # Exit the loop when GUI is closed
                else:
                    # Re-raise other exceptions
                    raise
            yield self.timeout(0.1)

    def run(self):
        """Starts visualisation process. Puts base run method to a Thread so that visualisation become main process.

           Args:

           Returns:
        """
        if self.visual:
            self.env.process(self._update_time())
            thr = Thread(target=super().run)
            thr.setDaemon(True)
            thr.start()
            self.tkplot.tk.mainloop()
        else:
            super().run()


###########################################################
# Snapshot Visualization Functions
###########################################################

def capture_simulation_window(sim_obj, snapshot_label, sim_time, log_callback=None, config_module=None):
    """Capture screenshot of the actual simulation window (Tkinter/topovis).
    
    This captures the real simulation visualization window that you see during runtime.
    
    Args:
        sim_obj: Simulator object
        snapshot_label (str): Label for this snapshot
        sim_time (float): Simulation time
        log_callback: Optional function to log messages (takes message string)
        config_module: Optional config module with SNAPSHOT_FOLDER setting
    """
    if not PIL_AVAILABLE:
        if log_callback:
            log_callback("⚠️  PIL/Pillow not available - cannot capture simulation window")
        raise Exception("PIL/Pillow not available")
    
    try:
        from PIL import ImageGrab
        import time
        
        # Try to get the Tkinter window from simulator
        root = None
        
        # Method 1: Direct access via sim.tk (most reliable)
        if hasattr(sim_obj, 'tk'):
            root = sim_obj.tk
            if log_callback:
                log_callback(f"   [WINDOW_CAPTURE] Found window via sim.tk")
        
        # Method 2: Access via sim.tkplot.tk
        elif hasattr(sim_obj, 'tkplot') and hasattr(sim_obj.tkplot, 'tk'):
            root = sim_obj.tkplot.tk
            if log_callback:
                log_callback(f"   [WINDOW_CAPTURE] Found window via sim.tkplot.tk")
        
        # Method 3: Try via scene.plotter
        elif hasattr(sim_obj, 'scene') and hasattr(sim_obj.scene, 'plotter'):
            plotter = sim_obj.scene.plotter
            if hasattr(plotter, 'tk'):
                root = plotter.tk
                if log_callback:
                    log_callback(f"   [WINDOW_CAPTURE] Found window via scene.plotter.tk")
            elif hasattr(plotter, 'root'):
                root = plotter.root
                if log_callback:
                    log_callback(f"   [WINDOW_CAPTURE] Found window via scene.plotter.root")
        
        if root is None:
            if log_callback:
                log_callback("⚠️  Could not find Tkinter window - using matplotlib fallback")
            raise Exception("Tkinter window not found")
        
        # Get window geometry - ensure window is ready
        root.update_idletasks()
        root.update()
        time.sleep(0.2)
        
        # Bring window to front and focus it (important for macOS)
        root.lift()
        root.focus_force()
        root.update()
        time.sleep(0.1)
        
        # Use winfo_rootx/y for screen coordinates (absolute)
        root_x = root.winfo_rootx()
        root_y = root.winfo_rooty()
        width = root.winfo_width()
        height = root.winfo_height()
        
        if log_callback:
            log_callback(f"   [WINDOW_CAPTURE] Window screen position: root_x={root_x}, root_y={root_y}, w={width}, h={height}")
        
        if width <= 0 or height <= 0:
            if log_callback:
                log_callback("⚠️  Window has invalid dimensions - using matplotlib fallback")
            raise Exception(f"Invalid window dimensions: {width}x{height}")
        
        if not root.winfo_viewable():
            if log_callback:
                log_callback("⚠️  Window is not visible - using matplotlib fallback")
            raise Exception("Window is not visible")
        
        # Try to find canvas widget
        canvas = None
        for widget in root.winfo_children():
            if 'canvas' in str(widget).lower() or 'Canvas' in str(type(widget)):
                canvas = widget
                break
            for child in widget.winfo_children():
                if 'canvas' in str(child).lower() or 'Canvas' in str(type(child)):
                    canvas = child
                    break
        
        if canvas:
            canvas_root_x = canvas.winfo_rootx()
            canvas_root_y = canvas.winfo_rooty()
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            
            if log_callback:
                log_callback(f"   [WINDOW_CAPTURE] Found canvas at screen: x={canvas_root_x}, y={canvas_root_y}, w={canvas_width}, h={canvas_height}")
            
            if canvas_width > 0 and canvas_height > 0:
                bbox = (canvas_root_x, canvas_root_y, canvas_root_x + canvas_width, canvas_root_y + canvas_height)
                if log_callback:
                    log_callback(f"   [WINDOW_CAPTURE] Capturing canvas area: {bbox}")
                screenshot = ImageGrab.grab(bbox=bbox)
            else:
                bbox = (root_x, root_y, root_x + width, root_y + height)
                if log_callback:
                    log_callback(f"   [WINDOW_CAPTURE] Canvas invalid, using full window: {bbox}")
                screenshot = ImageGrab.grab(bbox=bbox)
        else:
            bbox = (root_x, root_y, root_x + width, root_y + height)
            if log_callback:
                log_callback(f"   [WINDOW_CAPTURE] No canvas found, using full window: {bbox}")
            screenshot = ImageGrab.grab(bbox=bbox)
        
        # Ensure snapshot folder exists
        if config_module is None:
            try:
                from source import config
                config_module = config
            except:
                pass
        
        if config_module:
            snapshot_folder = _ensure_snapshot_folder(config_module)
        else:
            snapshot_folder = 'snapshots'
            if not os.path.exists(snapshot_folder):
                os.makedirs(snapshot_folder)
        
        # Save PNG file in snapshot folder
        safe_label = snapshot_label.replace(' ', '_').replace('-', '_')
        filename = os.path.join(snapshot_folder, f"snapshot_{safe_label}_{sim_time:.0f}s.png")
        screenshot.save(filename, 'PNG')
        
        if log_callback:
            log_callback(f"   💾 Saved simulation window screenshot: {filename}")
        
        return filename
        
    except Exception as e:
        if log_callback:
            log_callback(f"⚠️  Error capturing simulation window: {e}")
        raise


def save_snapshot_png(snapshot_label, sim_time, nodes, node_positions, orphaned_nodes, failed_nodes, 
                     role_name_func, config_module, log_callback=None):
    """Generate and save a PNG image of the network topology at snapshot time.
    
    Args:
        snapshot_label (str): Label for this snapshot
        sim_time (float): Simulation time
        nodes: List of all node objects
        node_positions: Dict of {node_id: (x, y)}
        orphaned_nodes: Set of orphaned node IDs
        failed_nodes: Set of failed node IDs
        role_name_func: Function to get role name (e.g., _role_name)
        config_module: Config module with NODE_TX_RANGE, FAILURE_HIGHLIGHT_DURATION, etc.
        log_callback: Optional function to log messages (takes message string)
    """
    if not MATPLOTLIB_AVAILABLE:
        if log_callback:
            log_callback("⚠️  Cannot generate PNG - matplotlib not available")
        return
    
    try:
        # Create figure
        fig, ax = plt.subplots(figsize=(16, 12))
        
        # Color mapping for roles (matching wsnlab_vis simulation colors)
        role_colors = {
            'ROOT': '#000000',           # Black
            'CLUSTER_HEAD': '#0000FF',   # Blue
            'ROUTER': '#FF00FF',         # Magenta/Pink
            'REGISTERED': '#00FF00',     # Green
            'UNREGISTERED': '#FFFF00',   # Yellow
            'UNDISCOVERED': '#C0C0C0',   # Light Gray
        }
        
        # Collect node data for plotting
        node_data = []
        for node in nodes:
            node_id = node.id
            role = getattr(node, 'role', None)
            role_name = role_name_func(role) if role_name_func else str(role)
            
            pos = node_positions.get(node_id, (None, None))
            if pos[0] is None:
                continue
            
            x, y = pos
            is_failed = node_id in failed_nodes
            is_orphan = node_id in orphaned_nodes
            parent_gui = getattr(node, 'parent_gui', None)
            
            # #region agent log
            if snapshot_label == "At_T1_Failure" and (is_failed or node_id in failed_nodes):
                import json, os
                try:
                    with open("/Users/krishnagajera/Project/Sem 3/wsn/EE662Fall2025_update1/.cursor/debug.log", "a") as f:
                        f.write(json.dumps({"location": "wsnlab_vis.py:443", "message": "Node in PNG generation", "data": {"node_id": node_id, "is_failed": is_failed, "failed_nodes_set": list(failed_nodes), "snapshot_label": snapshot_label}, "timestamp": __import__('datetime').datetime.now().timestamp(), "sessionId": "debug-session", "hypothesisId": "D"}) + "\n")
                except: pass
            # #endregion
            
            node_data.append({
                'id': node_id,
                'x': x,
                'y': y,
                'role': role_name,
                'is_failed': is_failed,
                'is_orphan': is_orphan,
                'parent': parent_gui,
                'node_obj': node  # Keep reference for failure_time check
            })
        
        if not node_data:
            if log_callback:
                log_callback("⚠️  No node positions available for PNG generation")
            plt.close(fig)
            return
        
        # Draw communication ranges (blue dashed circles)
        for node in node_data:
            if not node['is_failed']:
                circle = plt.Circle((node['x'], node['y']), config_module.NODE_TX_RANGE, 
                                  color='blue', fill=False, linestyle='--', 
                                  linewidth=0.5, alpha=0.3, zorder=0)
                ax.add_patch(circle)
        
        # Draw parent-child connections (green arrows)
        for node in node_data:
            if node['parent'] is not None and not node['is_failed']:
                parent_data = next((n for n in node_data if n['id'] == node['parent']), None)
                if parent_data and not parent_data['is_failed']:
                    dx = parent_data['x'] - node['x']
                    dy = parent_data['y'] - node['y']
                    ax.arrow(node['x'], node['y'], dx, dy,
                            head_width=8, head_length=6, fc='green', ec='green',
                            alpha=0.6, linewidth=1.5, zorder=1, length_includes_head=True)
        
        # Draw nodes
        for node in node_data:
            x, y = node['x'], node['y']
            role = node['role']
            color = role_colors.get(role, '#808080')
            
            # Adjust color for failed/orphan status - make them VERY obvious
            if node['is_failed']:
                node_obj = node['node_obj']
                # Always show failed nodes in bright red (they're in FAILED_NODES set)
                color = '#FF0000'  # Bright RED for failed nodes
                marker = 'X'
                size = 200
                # Check if recently failed (within highlight period) for extra emphasis
                if node_obj and hasattr(node_obj, 'failure_time') and node_obj.failure_time:
                    time_since_failure = sim_time - node_obj.failure_time
                    highlight_duration = getattr(config_module, 'FAILURE_HIGHLIGHT_DURATION', 10)
                    if time_since_failure > highlight_duration:
                        # Still red but slightly darker if highlight period passed
                        color = '#CC0000'
            elif node['is_orphan']:
                # Always show orphaned nodes in bright orange
                color = '#FF6600'  # Bright ORANGE for orphaned
                marker = '^'
                size = 120
            else:
                marker = 'o'
                size = 80
            
            ax.scatter(x, y, c=color, marker=marker, s=size, 
                      edgecolors='black', linewidths=1, zorder=2, alpha=0.8)
            
            # Add node ID label
            if node['id'] == 1:  # Always label ROOT
                ax.annotate(f"R{node['id']}", (x, y), xytext=(5, 5), 
                           textcoords='offset points', fontsize=8, fontweight='bold')
            elif role in ['CLUSTER_HEAD', 'ROUTER']:
                ax.annotate(f"{node['id']}", (x, y), xytext=(3, 3), 
                           textcoords='offset points', fontsize=7)
        
        # Set labels and title
        ax.set_xlabel('X Position (m)', fontsize=12)
        ax.set_ylabel('Y Position (m)', fontsize=12)
        title = f"Network Snapshot: {snapshot_label}\nTime: {sim_time:.2f}s"
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.2)
        ax.set_aspect('equal', adjustable='box')
        
        # Set background to match simulation (dark gray)
        ax.set_facecolor('#2F2F2F')
        fig.patch.set_facecolor('#2F2F2F')
        
        # Create legend
        legend_elements = []
        for role, color in role_colors.items():
            legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                                             markerfacecolor=color, markersize=10, 
                                             label=role, markeredgecolor='black', markeredgewidth=1))
        legend_elements.append(plt.Line2D([0], [0], marker='X', color='w', 
                                         markerfacecolor='#FF0000', markersize=14, 
                                         label='Failed (RED)', markeredgecolor='black', markeredgewidth=1))
        legend_elements.append(plt.Line2D([0], [0], marker='^', color='w', 
                                         markerfacecolor='#FF6600', markersize=12, 
                                         label='Orphan (ORANGE)', markeredgecolor='black', markeredgewidth=1))
        
        ax.legend(handles=legend_elements, loc='upper left', fontsize=9, framealpha=0.9)
        
        # Add statistics text box
        stats_text = f"Nodes: {len(node_data)}\n"
        stats_text += f"Failed: {len([n for n in node_data if n['is_failed']])}\n"
        stats_text += f"Orphans: {len([n for n in node_data if n['is_orphan']])}"
        
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
               fontsize=10, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        plt.tight_layout()
        
        # Ensure snapshot folder exists
        snapshot_folder = _ensure_snapshot_folder(config_module)
        
        # Save PNG file in snapshot folder
        safe_label = snapshot_label.replace(' ', '_').replace('-', '_')
        filename = os.path.join(snapshot_folder, f"snapshot_{safe_label}_{sim_time:.0f}s.png")
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        if log_callback:
            log_callback(f"   💾 Saved PNG: {filename}")
        
        return filename
        
    except Exception as e:
        if log_callback:
            log_callback(f"⚠️  Error in save_snapshot_png: {e}")
            import traceback
            traceback.print_exc()
        try:
            plt.close('all')
        except:
            pass
        raise
