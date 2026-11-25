use eframe::egui;
use serde_json::Value;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Seek, SeekFrom};
use std::path::PathBuf;
use std::sync::mpsc::{channel, Receiver, Sender};
use std::thread;
use std::time::Instant;

#[derive(Clone)]
struct ChatEntry {
    step: i64,
    source: String,
    content: String,
    tool_calls: Vec<String>,
}

#[derive(Clone)]
struct RunningTask {
    task_id: String,
    size_bytes: u64,
    last_log_line: String,
}

#[derive(Clone)]
struct ChatMessage {
    sender: String,
    text: String,
    timestamp: String,
    is_streaming: bool,
    avatar_color: egui::Color32,
    bubble_bg: egui::Color32,
}

pub struct ImfApp {
    // Navigation
    active_nav: usize, // 0: Council of Models, 1: Antigravity Twin Studio (IMF & WEFT), 2: Fast Interactive Chat
    
    // Antigravity transcripts
    imf_entries: Vec<ChatEntry>,
    weft_entries: Vec<ChatEntry>,
    running_tasks: Vec<RunningTask>,

    // Interactive Solo Chat
    solo_input: String,
    solo_history: Vec<ChatMessage>,
    selected_solo_model: String,
    is_solo_generating: bool,

    // Council Tab
    council_input: String,
    council_history: Vec<ChatMessage>,
    active_council_models: Vec<String>,
    is_council_generating: bool,

    // Communication channels
    solo_tx: Sender<(String, bool)>,
    solo_rx: Receiver<(String, bool)>,
    council_tx: Sender<(String, String, bool)>, // (model_name, chunk, is_done)
    council_rx: Receiver<(String, String, bool)>,

    // Internal state
    last_sync: Instant,
    sync_status: String,
    archive_dir: PathBuf,
}

impl Default for ImfApp {
    fn default() -> Self {
        let dir = PathBuf::from("imf_gui/generated_items");
        let _ = fs::create_dir_all(&dir);

        let (solo_tx, solo_rx) = channel();
        let (council_tx, council_rx) = channel();

        let mut app = Self {
            active_nav: 0, // Default to Council of Models tab
            imf_entries: Vec::new(),
            weft_entries: Vec::new(),
            running_tasks: Vec::new(),
            solo_input: String::new(),
            solo_history: vec![ChatMessage {
                sender: String::from("IMF Neural Coprocessor"),
                text: String::from("IMF Studio engine ready. Select any local foundation model below or switch to the Council to query them all in parallel."),
                timestamp: chrono::Local::now().format("%H:%M:%S").to_string(),
                is_streaming: false,
                avatar_color: egui::Color32::from_rgb(0, 210, 255),
                bubble_bg: egui::Color32::from_rgb(18, 28, 45),
            }],
            selected_solo_model: String::from("qwen2.5:14b"),
            is_solo_generating: false,
            council_input: String::new(),
            council_history: Vec::new(),
            active_council_models: vec![
                String::from("qwen3.8-27b:latest"),
                String::from("qwen2.5:14b"),
                String::from("qwen2.5vl:7b"),
            ],
            is_council_generating: false,
            solo_tx,
            solo_rx,
            council_tx,
            council_rx,
            last_sync: Instant::now(),
            sync_status: String::from("Synchronizing..."),
            archive_dir: dir,
        };
        app.refresh_all_antigravity();
        app
    }
}

impl ImfApp {
    fn parse_transcript(path: &PathBuf) -> Vec<ChatEntry> {
        let mut parsed = Vec::new();
        if let Ok(mut file) = File::open(path) {
            let meta = file.metadata().ok();
            let file_size = meta.map(|m| m.len()).unwrap_or(0);
            let seek_pos = if file_size > 250_000 { file_size - 250_000 } else { 0 };
            let _ = file.seek(SeekFrom::Start(seek_pos));
            let reader = BufReader::new(file);

            for line in reader.lines().flatten() {
                if let Ok(v) = serde_json::from_str::<Value>(&line) {
                    let step = v.get("step_index").and_then(|s| s.as_i64()).unwrap_or(0);
                    let source = v.get("source").and_then(|s| s.as_str()).unwrap_or("SYS").to_string();
                    let content = v.get("content").and_then(|c| c.as_str()).unwrap_or("").to_string();

                    let mut tools = Vec::new();
                    if let Some(t_array) = v.get("tool_calls").and_then(|t| t.as_array()) {
                        for t in t_array {
                            if let Some(name) = t.get("name").and_then(|n| n.as_str()) {
                                tools.push(name.to_string());
                            }
                        }
                    }

                    if !content.is_empty() || !tools.is_empty() {
                        parsed.push(ChatEntry { step, source, content, tool_calls: tools });
                    }
                }
            }
        }
        if parsed.len() > 30 {
            let len = parsed.len();
            parsed[len - 30..].to_vec()
        } else {
            parsed
        }
    }

    fn refresh_all_antigravity(&mut self) {
        let imf_path = PathBuf::from("/home/akarta/.gemini/antigravity/brain/709ff001-bb91-4c96-a70e-71e9c075fc42/.system_generated/logs/transcript.jsonl");
        let weft_path = PathBuf::from("/home/akarta/.gemini/antigravity/brain/d4834979-e7d4-45b3-9ac6-cc58e7f42d7c/.system_generated/logs/transcript.jsonl");
        let tasks_dir = PathBuf::from("/home/akarta/.gemini/antigravity/brain/709ff001-bb91-4c96-a70e-71e9c075fc42/.system_generated/tasks");

        self.imf_entries = Self::parse_transcript(&imf_path);
        self.weft_entries = Self::parse_transcript(&weft_path);

        if let Ok(entries) = fs::read_dir(&tasks_dir) {
            let mut tasks = Vec::new();
            let mut file_list: Vec<_> = entries
                .flatten()
                .filter(|e| e.path().extension().map_or(false, |ext| ext == "log"))
                .collect();

            file_list.sort_by_key(|e| e.metadata().and_then(|m| m.modified()).ok());
            file_list.reverse();

            for e in file_list.into_iter().take(6) {
                let name = e.file_name().to_string_lossy().to_string();
                let meta = e.metadata().ok();
                let size = meta.as_ref().map(|m| m.len()).unwrap_or(0);

                let mut last_line = String::from("(waiting for output)");
                if let Ok(f) = File::open(e.path()) {
                    let r = BufReader::new(f);
                    let lines: Vec<_> = r.lines().flatten().collect();
                    if let Some(l) = lines.last() {
                        last_line = l.chars().take(75).collect();
                    }
                }

                tasks.push(RunningTask { task_id: name, size_bytes: size, last_log_line: last_line });
            }
            self.running_tasks = tasks;
        }

        self.last_sync = Instant::now();
        self.sync_status = format!("Live Sync: {}", chrono::Local::now().format("%H:%M:%S"));
    }

    fn send_solo_chat(&mut self) {
        let text = self.solo_input.trim().to_string();
        if text.is_empty() { return; }

        let now_str = chrono::Local::now().format("%H:%M:%S").to_string();
        self.solo_history.push(ChatMessage {
            sender: String::from("You"),
            text: text.clone(),
            timestamp: now_str.clone(),
            is_streaming: false,
            avatar_color: egui::Color32::from_rgb(0, 230, 180),
            bubble_bg: egui::Color32::from_rgb(20, 36, 32),
        });

        let model = self.selected_solo_model.clone();
        self.solo_history.push(ChatMessage {
            sender: model.clone(),
            text: String::new(),
            timestamp: now_str,
            is_streaming: true,
            avatar_color: egui::Color32::from_rgb(120, 170, 255),
            bubble_bg: egui::Color32::from_rgb(20, 28, 46),
        });

        self.solo_input.clear();
        self.is_solo_generating = true;

        let prompt = text.clone();
        let tx = self.solo_tx.clone();
        let out_dir = self.archive_dir.clone();

        thread::spawn(move || {
            let client = reqwest::blocking::Client::builder()
                .timeout(std::time::Duration::from_secs(90))
                .build().unwrap();

            let payload = serde_json::json!({
                "model": model,
                "prompt": prompt,
                "stream": true
            });

            let mut full_resp = String::new();
            if let Ok(resp) = client.post("http://127.0.0.1:11434/api/generate").json(&payload).send() {
                let reader = BufReader::new(resp);
                for line in reader.lines().flatten() {
                    if let Ok(v) = serde_json::from_str::<Value>(&line) {
                        if let Some(tok) = v.get("response").and_then(|r| r.as_str()) {
                            full_resp.push_str(tok);
                            let _ = tx.send((tok.to_string(), false));
                        }
                        if v.get("done").and_then(|d| d.as_bool()).unwrap_or(false) {
                            break;
                        }
                    }
                }
            } else {
                let err = "[Ollama daemon unreachable on port 11434]";
                full_resp.push_str(err);
                let _ = tx.send((err.to_string(), false));
            }
            let _ = tx.send((String::new(), true));

            // Log turn
            let now = chrono::Local::now();
            let out_file = out_dir.join(format!("solo_turn_{}.json", now.format("%Y%m%d_%H%M%S")));
            let log_data = serde_json::json!({
                "timestamp": now.to_rfc3339(),
                "model": model,
                "prompt": prompt,
                "response": full_resp
            });
            let _ = fs::write(out_file, serde_json::to_string_pretty(&log_data).unwrap());
        });
    }

    fn send_council_query(&mut self) {
        let text = self.council_input.trim().to_string();
        if text.is_empty() { return; }

        let now_str = chrono::Local::now().format("%H:%M:%S").to_string();
        self.council_history.push(ChatMessage {
            sender: String::from("Commander"),
            text: text.clone(),
            timestamp: now_str.clone(),
            is_streaming: false,
            avatar_color: egui::Color32::from_rgb(255, 180, 50),
            bubble_bg: egui::Color32::from_rgb(38, 28, 14),
        });

        self.council_input.clear();
        self.is_council_generating = true;

        let models = self.active_council_models.clone();
        for m in &models {
            self.council_history.push(ChatMessage {
                sender: format!("Council: {}", m),
                text: String::new(),
                timestamp: now_str.clone(),
                is_streaming: true,
                avatar_color: match m.as_str() {
                    "qwen3.8-27b:latest" => egui::Color32::from_rgb(255, 90, 150),
                    "qwen2.5:14b" => egui::Color32::from_rgb(70, 210, 255),
                    _ => egui::Color32::from_rgb(150, 120, 255),
                },
                bubble_bg: egui::Color32::from_rgb(22, 24, 36),
            });
        }

        let prompt = text.clone();
        let tx = self.council_tx.clone();

        for m in models {
            let p = prompt.clone();
            let m_name = m.clone();
            let tx_sub = tx.clone();

            thread::spawn(move || {
                let client = reqwest::blocking::Client::builder()
                    .timeout(std::time::Duration::from_secs(120))
                    .build().unwrap();

                let payload = serde_json::json!({
                    "model": m_name,
                    "prompt": p,
                    "stream": true
                });

                if let Ok(resp) = client.post("http://127.0.0.1:11434/api/generate").json(&payload).send() {
                    let reader = BufReader::new(resp);
                    for line in reader.lines().flatten() {
                        if let Ok(v) = serde_json::from_str::<Value>(&line) {
                            if let Some(tok) = v.get("response").and_then(|r| r.as_str()) {
                                let _ = tx_sub.send((m_name.clone(), tok.to_string(), false));
                            }
                            if v.get("done").and_then(|d| d.as_bool()).unwrap_or(false) {
                                break;
                            }
                        }
                    }
                } else {
                    let _ = tx_sub.send((m_name.clone(), "[Ollama model busy or unreachable]".to_string(), false));
                }
                let _ = tx_sub.send((m_name.clone(), String::new(), true));
            });
        }
    }
}

impl eframe::App for ImfApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Drain solo streaming
        while let Ok((tok, done)) = self.solo_rx.try_recv() {
            if done {
                if let Some(msg) = self.solo_history.last_mut() {
                    msg.is_streaming = false;
                }
                self.is_solo_generating = false;
            } else {
                if let Some(msg) = self.solo_history.last_mut() {
                    msg.text.push_str(&tok);
                }
            }
            ctx.request_repaint();
        }

        // Drain council streaming
        while let Ok((m_name, tok, done)) = self.council_rx.try_recv() {
            for msg in self.council_history.iter_mut().rev() {
                if msg.sender.contains(&m_name) && msg.is_streaming {
                    if done {
                        msg.is_streaming = false;
                    } else {
                        msg.text.push_str(&tok);
                    }
                    break;
                }
            }
            // Check if all finished
            if !self.council_history.iter().any(|m| m.is_streaming) {
                self.is_council_generating = false;
            }
            ctx.request_repaint();
        }

        // Auto-refresh Antigravity transcripts
        if self.last_sync.elapsed().as_secs() >= 3 {
            self.refresh_all_antigravity();
            ctx.request_repaint();
        }

        // High-End Cyberpunk / Dark Obsidian Studio Palette
        let mut visuals = egui::Visuals::dark();
        visuals.panel_fill = egui::Color32::from_rgb(11, 13, 19);
        visuals.window_fill = egui::Color32::from_rgb(14, 17, 24);
        visuals.widgets.noninteractive.bg_fill = egui::Color32::from_rgb(18, 22, 32);
        visuals.widgets.inactive.bg_fill = egui::Color32::from_rgb(22, 28, 40);
        visuals.widgets.hovered.bg_fill = egui::Color32::from_rgb(34, 44, 62);
        visuals.widgets.active.bg_fill = egui::Color32::from_rgb(45, 60, 85);
        ctx.set_visuals(visuals);

        egui::CentralPanel::default().show(ctx, |ui| {
            // Master Navigation Top Bar
            egui::Frame::group(ui.style())
                .fill(egui::Color32::from_rgb(16, 20, 30))
                .inner_margin(egui::Margin::symmetric(14.0, 8.0))
                .rounding(egui::Rounding::same(8.0))
                .show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new("⚡ IMF OMNI-STUDIO").color(egui::Color32::from_rgb(0, 230, 200)).strong().size(18.0));
                        ui.add_space(20.0);

                        // Tab 0: Council of Models
                        let c_sel = self.active_nav == 0;
                        if ui.selectable_label(c_sel, egui::RichText::new("👑 Council of Models").size(14.0).strong()).clicked() {
                            self.active_nav = 0;
                        }

                        // Tab 1: Antigravity Twin Feeds
                        let a_sel = self.active_nav == 1;
                        if ui.selectable_label(a_sel, egui::RichText::new("📡 Antigravity Sessions (IMF & WEFT)").size(14.0).strong()).clicked() {
                            self.active_nav = 1;
                        }

                        // Tab 2: Fast Interactive Chat
                        let f_sel = self.active_nav == 2;
                        if ui.selectable_label(f_sel, egui::RichText::new("⚡ Fast Solo Chat").size(14.0).strong()).clicked() {
                            self.active_nav = 2;
                        }

                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            ui.label(egui::RichText::new(&self.sync_status).color(egui::Color32::from_rgb(120, 160, 200)).size(11.0));
                            if ui.button("🔄 Sync").clicked() {
                                self.refresh_all_antigravity();
                            }
                        });
                    });
                });

            ui.add_space(8.0);

            // ==========================================
            // TAB 0: COUNCIL OF MODELS
            // ==========================================
            if self.active_nav == 0 {
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new("Active Council:").color(egui::Color32::LIGHT_GRAY));
                    ui.colored_label(egui::Color32::from_rgb(255, 100, 160), "◆ Qwen 27B Reasoning");
                    ui.colored_label(egui::Color32::from_rgb(70, 210, 255), "◆ Qwen 14B Systems/Math");
                    ui.colored_label(egui::Color32::from_rgb(160, 140, 255), "◆ Qwen 7B Multimodal");
                    if self.is_council_generating {
                        ui.colored_label(egui::Color32::from_rgb(255, 200, 50), "⚡ Convening Council in parallel...");
                    }
                });

                ui.separator();

                let avail_h = ui.available_height() - 75.0;
                egui::ScrollArea::vertical()
                    .max_height(avail_h)
                    .stick_to_bottom(true)
                    .show(ui, |ui| {
                        if self.council_history.is_empty() {
                            ui.vertical_centered(|ui| {
                                ui.add_space(60.0);
                                ui.label(egui::RichText::new("👑 The Council of Models is assembled.").color(egui::Color32::GRAY).size(16.0));
                                ui.label("Broadcast any question below. All 3 local foundation models will analyze, deliberate, and answer concurrently.");
                            });
                        }

                        for msg in &self.council_history {
                            egui::Frame::group(ui.style())
                                .fill(msg.bubble_bg)
                                .inner_margin(egui::Margin::same(12.0))
                                .rounding(egui::Rounding::same(8.0))
                                .show(ui, |ui| {
                                    ui.horizontal(|ui| {
                                        ui.colored_label(msg.avatar_color, egui::RichText::new(&msg.sender).strong().size(13.0));
                                        ui.weak(&msg.timestamp);
                                        if msg.is_streaming {
                                            ui.colored_label(egui::Color32::from_rgb(255, 180, 50), "✦ streaming...");
                                        }
                                    });
                                    ui.add_space(4.0);
                                    ui.label(egui::RichText::new(&msg.text).size(13.5));
                                });
                            ui.add_space(6.0);
                        }
                    });

                ui.separator();

                ui.horizontal(|ui| {
                    let text_edit = ui.add(
                        egui::TextEdit::singleline(&mut self.council_input)
                            .hint_text("Ask the Council anything across engineering, coding, mathematics, or philosophy...")
                            .desired_width(ui.available_width() - 110.0),
                    );

                    let enter = text_edit.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter));
                    if ui.button(egui::RichText::new("👑 Convene").color(egui::Color32::from_rgb(255, 200, 80)).strong()).clicked() || enter {
                        self.send_council_query();
                    }
                });

            // ==========================================
            // TAB 1: ANTIGRAVITY TWIN FEEDS (SEPARATE COLUMNS)
            // ==========================================
            } else if self.active_nav == 1 {
                let col_h = ui.available_height() - 10.0;
                ui.columns(3, |cols| {
                    // Column 1: IMF Feed
                    egui::Frame::group(cols[0].style())
                        .fill(egui::Color32::from_rgb(14, 18, 28))
                        .inner_margin(egui::Margin::same(10.0))
                        .rounding(egui::Rounding::same(8.0))
                        .show(&mut cols[0], |ui| {
                            ui.horizontal(|ui| {
                                ui.label(egui::RichText::new("🔬 IMF SESSION").color(egui::Color32::from_rgb(70, 200, 255)).strong().size(14.0));
                                ui.weak("(709ff001)");
                            });
                            ui.separator();

                            egui::ScrollArea::vertical()
                                .max_height(col_h - 40.0)
                                .stick_to_bottom(true)
                                .show(ui, |ui| {
                                    for m in &self.imf_entries {
                                        let col = match m.source.as_str() {
                                            "USER_EXPLICIT" => egui::Color32::from_rgb(0, 230, 200),
                                            "MODEL" => egui::Color32::from_rgb(140, 255, 140),
                                            _ => egui::Color32::from_rgb(255, 210, 80),
                                        };
                                        egui::Frame::group(ui.style())
                                            .fill(egui::Color32::from_rgb(20, 26, 40))
                                            .inner_margin(egui::Margin::same(6.0))
                                            .rounding(egui::Rounding::same(6.0))
                                            .show(ui, |ui| {
                                                ui.colored_label(col, format!("[#{}] {}", m.step, m.source));
                                                if !m.content.is_empty() {
                                                    let p: String = m.content.chars().take(240).collect();
                                                    ui.label(&p);
                                                }
                                                if !m.tool_calls.is_empty() {
                                                    ui.weak(format!("🔧 {}", m.tool_calls.join(", ")));
                                                }
                                            });
                                        ui.add_space(4.0);
                                    }
                                });
                        });

                    // Column 2: WEFT Feed
                    egui::Frame::group(cols[1].style())
                        .fill(egui::Color32::from_rgb(24, 16, 24))
                        .inner_margin(egui::Margin::same(10.0))
                        .rounding(egui::Rounding::same(8.0))
                        .show(&mut cols[1], |ui| {
                            ui.horizontal(|ui| {
                                ui.label(egui::RichText::new("🧵 WEFT SESSION").color(egui::Color32::from_rgb(255, 130, 200)).strong().size(14.0));
                                ui.weak("(d4834979)");
                            });
                            ui.separator();

                            egui::ScrollArea::vertical()
                                .max_height(col_h - 40.0)
                                .stick_to_bottom(true)
                                .show(ui, |ui| {
                                    for m in &self.weft_entries {
                                        let col = match m.source.as_str() {
                                            "USER_EXPLICIT" => egui::Color32::from_rgb(255, 160, 220),
                                            "MODEL" => egui::Color32::from_rgb(255, 210, 140),
                                            _ => egui::Color32::from_rgb(200, 200, 100),
                                        };
                                        egui::Frame::group(ui.style())
                                            .fill(egui::Color32::from_rgb(32, 22, 34))
                                            .inner_margin(egui::Margin::same(6.0))
                                            .rounding(egui::Rounding::same(6.0))
                                            .show(ui, |ui| {
                                                ui.colored_label(col, format!("[#{}] {}", m.step, m.source));
                                                if !m.content.is_empty() {
                                                    let p: String = m.content.chars().take(240).collect();
                                                    ui.label(&p);
                                                }
                                                if !m.tool_calls.is_empty() {
                                                    ui.weak(format!("🔧 {}", m.tool_calls.join(", ")));
                                                }
                                            });
                                        ui.add_space(4.0);
                                    }
                                });
                        });

                    // Column 3: Active Background Tasks
                    egui::Frame::group(cols[2].style())
                        .fill(egui::Color32::from_rgb(18, 20, 26))
                        .inner_margin(egui::Margin::same(10.0))
                        .rounding(egui::Rounding::same(8.0))
                        .show(&mut cols[2], |ui| {
                            ui.horizontal(|ui| {
                                ui.label(egui::RichText::new("⚙ ACTIVE TASKS").color(egui::Color32::from_rgb(255, 190, 80)).strong().size(14.0));
                                ui.weak(format!("({})", self.running_tasks.len()));
                            });
                            ui.separator();

                            egui::ScrollArea::vertical()
                                .max_height(col_h - 40.0)
                                .show(ui, |ui| {
                                    for t in &self.running_tasks {
                                        egui::Frame::group(ui.style())
                                            .fill(egui::Color32::from_rgb(26, 30, 40))
                                            .inner_margin(egui::Margin::same(8.0))
                                            .rounding(egui::Rounding::same(6.0))
                                            .show(ui, |ui| {
                                                ui.horizontal(|ui| {
                                                    ui.strong(&t.task_id);
                                                    ui.weak(format!("{} KB", t.size_bytes / 1024));
                                                });
                                                ui.add_space(2.0);
                                                ui.colored_label(egui::Color32::from_rgb(160, 200, 240), &t.last_log_line);
                                            });
                                        ui.add_space(4.0);
                                    }
                                });
                        });
                });

            // ==========================================
            // TAB 2: FAST INTERACTIVE SOLO CHAT
            // ==========================================
            } else {
                ui.horizontal(|ui| {
                    ui.label("Selected Solo Model:");
                    egui::ComboBox::from_label("")
                        .selected_text(&self.selected_solo_model)
                        .show_ui(ui, |ui| {
                            ui.selectable_value(&mut self.selected_solo_model, String::from("qwen2.5:14b"), "qwen2.5:14b (Recommended: Fast & Accurate)");
                            ui.selectable_value(&mut self.selected_solo_model, String::from("qwen3.8-27b:latest"), "qwen3.8-27b:latest (Heavy 27B Reasoning)");
                            ui.selectable_value(&mut self.selected_solo_model, String::from("qwen2.5vl:7b"), "qwen2.5vl:7b (Vision-Language)");
                        });

                    if self.is_solo_generating {
                        ui.colored_label(egui::Color32::from_rgb(0, 230, 200), "⚡ Streaming tokens live...");
                    }
                });

                ui.separator();

                let avail_h = ui.available_height() - 70.0;
                egui::ScrollArea::vertical()
                    .max_height(avail_h)
                    .stick_to_bottom(true)
                    .show(ui, |ui| {
                        for msg in &self.solo_history {
                            egui::Frame::group(ui.style())
                                .fill(msg.bubble_bg)
                                .inner_margin(egui::Margin::same(10.0))
                                .rounding(egui::Rounding::same(8.0))
                                .show(ui, |ui| {
                                    ui.horizontal(|ui| {
                                        ui.colored_label(msg.avatar_color, egui::RichText::new(&msg.sender).strong());
                                        ui.weak(&msg.timestamp);
                                        if msg.is_streaming {
                                            ui.colored_label(egui::Color32::from_rgb(255, 180, 50), "✦ typing...");
                                        }
                                    });
                                    ui.add_space(2.0);
                                    ui.label(&msg.text);
                                });
                            ui.add_space(6.0);
                        }
                    });

                ui.separator();

                ui.horizontal(|ui| {
                    let text_edit = ui.add(
                        egui::TextEdit::singleline(&mut self.solo_input)
                            .hint_text("Ask anything...")
                            .desired_width(ui.available_width() - 95.0),
                    );

                    let enter = text_edit.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter));
                    if ui.button("➤ Send").clicked() || enter {
                        self.send_solo_chat();
                    }
                });
            }
        });
    }
}

fn main() -> eframe::Result<()> {
    let native_options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1200.0, 750.0])
            .with_min_inner_size([880.0, 540.0])
            .with_title("IMF Omni-Studio & Model Council"),
        ..Default::default()
    };
    eframe::run_native(
        "IMF Studio",
        native_options,
        Box::new(|_cc| Ok(Box::new(ImfApp::default()))),
    )
}
