use eframe::egui;
use serde_json::Value;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Seek, SeekFrom};
use std::path::PathBuf;
use std::process::Command;
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
struct UserMessage {
    sender: String,
    text: String,
    timestamp: String,
    is_streaming: bool,
}

#[derive(Clone, PartialEq)]
enum ModelBackend {
    Ollama(String),
    HuggingFace(String),
}

#[derive(Clone, PartialEq)]
enum ConversationSource {
    IMF,
    WEFT,
}

pub struct ImfApp {
    chat_input: String,
    selected_main_tab: usize,       // 0: Antigravity Session Logs, 1: Live Interactive Chat, 2: Math/Lean Studio
    selected_convo_tab: ConversationSource, // IMF vs WEFT in Antigravity viewer
    chat_entries: Vec<ChatEntry>,
    running_tasks: Vec<RunningTask>,
    user_chat_history: Vec<UserMessage>,
    generated_items_dir: PathBuf,
    selected_model: ModelBackend,
    output_count: usize,
    last_refresh: Instant,
    log_status: String,
    is_generating: bool,
    tx: Sender<(String, bool)>,     // (token_or_full_text, is_done)
    rx: Receiver<(String, bool)>,
}

impl Default for ImfApp {
    fn default() -> Self {
        let dir = PathBuf::from("imf_gui/generated_items");
        let _ = fs::create_dir_all(&dir);
        let (tx, rx) = channel();

        let mut app = Self {
            chat_input: String::new(),
            selected_main_tab: 1, // Default to Live Interactive Chat
            selected_convo_tab: ConversationSource::IMF,
            chat_entries: Vec::new(),
            running_tasks: Vec::new(),
            user_chat_history: vec![UserMessage {
                sender: String::from("🤖 Assistant"),
                text: String::from("Welcome to the modernized IMF & WEFT Neural-Symbolic Studio! You can stream live tokens from local models (Qwen 27B / 14B / 7B-VL or Hugging Face local weights), switch between IMF and WEFT project logs, or inspect active background tasks in real time."),
                timestamp: chrono::Local::now().format("%H:%M:%S").to_string(),
                is_streaming: false,
            }],
            generated_items_dir: dir,
            selected_model: ModelBackend::Ollama(String::from("qwen2.5:14b")), // Default to fast 14B model
            output_count: 0,
            last_refresh: Instant::now(),
            log_status: String::from("Initializing..."),
            is_generating: false,
            tx,
            rx,
        };
        app.refresh_antigravity_state();
        app
    }
}

impl ImfApp {
    fn get_active_transcript_path(&self) -> PathBuf {
        let conv_id = match self.selected_convo_tab {
            ConversationSource::IMF => "709ff001-bb91-4c96-a70e-71e9c075fc42",
            ConversationSource::WEFT => "d4834979-e7d4-45b3-9ac6-cc58e7f42d7c",
        };
        PathBuf::from(format!(
            "/home/akarta/.gemini/antigravity/brain/{}/.system_generated/logs/transcript.jsonl",
            conv_id
        ))
    }

    fn refresh_antigravity_state(&mut self) {
        let transcript_path = self.get_active_transcript_path();
        let tasks_dir = PathBuf::from(
            "/home/akarta/.gemini/antigravity/brain/709ff001-bb91-4c96-a70e-71e9c075fc42/.system_generated/tasks",
        );

        if let Ok(mut file) = File::open(&transcript_path) {
            let meta = file.metadata().ok();
            let file_size = meta.map(|m| m.len()).unwrap_or(0);
            let seek_pos = if file_size > 300_000 {
                file_size - 300_000
            } else {
                0
            };
            let _ = file.seek(SeekFrom::Start(seek_pos));
            let reader = BufReader::new(file);

            let mut parsed = Vec::new();
            for line in reader.lines().flatten() {
                if let Ok(v) = serde_json::from_str::<Value>(&line) {
                    let step = v.get("step_index").and_then(|s| s.as_i64()).unwrap_or(0);
                    let source = v
                        .get("source")
                        .and_then(|s| s.as_str())
                        .unwrap_or("UNKNOWN")
                        .to_string();
                    let content = v
                        .get("content")
                        .and_then(|c| c.as_str())
                        .unwrap_or("")
                        .to_string();

                    let mut tools = Vec::new();
                    if let Some(t_array) = v.get("tool_calls").and_then(|t| t.as_array()) {
                        for t in t_array {
                            if let Some(name) = t.get("name").and_then(|n| n.as_str()) {
                                tools.push(name.to_string());
                            }
                        }
                    }

                    if !content.is_empty() || !tools.is_empty() {
                        parsed.push(ChatEntry {
                            step,
                            source,
                            content,
                            tool_calls: tools,
                        });
                    }
                }
            }

            if parsed.len() > 35 {
                let len = parsed.len();
                self.chat_entries = parsed[len - 35..].to_vec();
            } else {
                self.chat_entries = parsed;
            }
        }

        // Active background tasks
        if let Ok(entries) = fs::read_dir(&tasks_dir) {
            let mut tasks = Vec::new();
            let mut file_list: Vec<_> = entries
                .flatten()
                .filter(|e| e.path().extension().map_or(false, |ext| ext == "log"))
                .collect();

            file_list.sort_by_key(|e| e.metadata().and_then(|m| m.modified()).ok());
            file_list.reverse();

            for e in file_list.into_iter().take(8) {
                let name = e.file_name().to_string_lossy().to_string();
                let meta = e.metadata().ok();
                let size = meta.as_ref().map(|m| m.len()).unwrap_or(0);

                let mut last_line = String::from("(waiting for output)");
                if let Ok(f) = File::open(e.path()) {
                    let r = BufReader::new(f);
                    let lines: Vec<_> = r.lines().flatten().collect();
                    if let Some(l) = lines.last() {
                        last_line = l.chars().take(85).collect();
                    }
                }

                tasks.push(RunningTask {
                    task_id: name,
                    size_bytes: size,
                    last_log_line: last_line,
                });
            }
            self.running_tasks = tasks;
        }

        self.last_refresh = Instant::now();
        self.log_status = format!(
            "Synced {}",
            chrono::Local::now().format("%H:%M:%S")
        );
    }

    fn send_chat_message(&mut self) {
        let text = self.chat_input.trim().to_string();
        if text.is_empty() {
            return;
        }

        let now_str = chrono::Local::now().format("%H:%M:%S").to_string();
        self.user_chat_history.push(UserMessage {
            sender: String::from("👤 You"),
            text: text.clone(),
            timestamp: now_str.clone(),
            is_streaming: false,
        });

        // Placeholder for streaming reply
        let model_name = match &self.selected_model {
            ModelBackend::Ollama(m) => m.clone(),
            ModelBackend::HuggingFace(hf) => hf.clone(),
        };

        self.user_chat_history.push(UserMessage {
            sender: format!("🤖 {}", model_name),
            text: String::new(),
            timestamp: now_str,
            is_streaming: true,
        });

        self.chat_input.clear();
        self.is_generating = true;

        let model_choice = self.selected_model.clone();
        let prompt = text.clone();
        let tx = self.tx.clone();
        let out_dir = self.generated_items_dir.clone();

        self.output_count += 1;
        let count = self.output_count;

        thread::spawn(move || {
            let mut full_accumulated = String::new();

            match model_choice {
                ModelBackend::Ollama(ref m) => {
                    let client = reqwest::blocking::Client::builder()
                        .timeout(std::time::Duration::from_secs(90))
                        .build()
                        .unwrap();

                    let payload = serde_json::json!({
                        "model": m,
                        "prompt": prompt,
                        "stream": true
                    });

                    if let Ok(resp) = client.post("http://127.0.0.1:11434/api/generate").json(&payload).send() {
                        let reader = BufReader::new(resp);
                        for line in reader.lines().flatten() {
                            if let Ok(v) = serde_json::from_str::<Value>(&line) {
                                if let Some(tok) = v.get("response").and_then(|r| r.as_str()) {
                                    full_accumulated.push_str(tok);
                                    let _ = tx.send((tok.to_string(), false));
                                }
                                if v.get("done").and_then(|d| d.as_bool()).unwrap_or(false) {
                                    break;
                                }
                            }
                        }
                    } else {
                        let err = "[Error: Ollama daemon is unreachable]";
                        full_accumulated.push_str(err);
                        let _ = tx.send((err.to_string(), false));
                    }
                }
                ModelBackend::HuggingFace(ref hf_tag) => {
                    let output = Command::new("uv")
                        .args([
                            "run",
                            "python",
                            "scripts/imf_model_cli_infer.py",
                            "--engine",
                            "hf",
                            "--target",
                            hf_tag,
                            "--prompt",
                            &prompt,
                            "--max_tokens",
                            "96",
                        ])
                        .output();

                    let text = match output {
                        Ok(o) => {
                            if o.status.success() {
                                let stdout = String::from_utf8_lossy(&o.stdout);
                                if let Ok(val) = serde_json::from_str::<Value>(&stdout) {
                                    val.get("response")
                                        .and_then(|r| r.as_str())
                                        .unwrap_or("Empty response")
                                        .to_string()
                                } else {
                                    stdout.to_string()
                                }
                            } else {
                                format!(
                                    "[Error running HF model: {}]",
                                    String::from_utf8_lossy(&o.stderr)
                                )
                            }
                        }
                        Err(e) => format!("[Execution Error: {}]", e),
                    };
                    full_accumulated.push_str(&text);
                    let _ = tx.send((text, false));
                }
            }

            // Signal end of stream
            let _ = tx.send((String::new(), true));

            // Archive conversation turn
            let now = chrono::Local::now();
            let out_file = out_dir.join(format!(
                "chat_turn_{:04}_{}.json",
                count,
                now.format("%Y%m%d_%H%M%S")
            ));
            let log_payload = serde_json::json!({
                "id": count,
                "model": model_name,
                "timestamp": now.to_rfc3339(),
                "user_prompt": prompt,
                "response": full_accumulated
            });
            let _ = fs::write(out_file, serde_json::to_string_pretty(&log_payload).unwrap());
        });
    }
}

impl eframe::App for ImfApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Handle streamed tokens
        while let Ok((chunk, is_done)) = self.rx.try_recv() {
            if is_done {
                if let Some(last) = self.user_chat_history.last_mut() {
                    last.is_streaming = false;
                }
                self.is_generating = false;
            } else {
                if let Some(last) = self.user_chat_history.last_mut() {
                    last.text.push_str(&chunk);
                }
            }
            ctx.request_repaint();
        }

        // Periodic transcript refresh
        if self.last_refresh.elapsed().as_secs() >= 3 {
            self.refresh_antigravity_state();
            ctx.request_repaint();
        }

        // Custom Visual Styling (Dark Studio Theme)
        let mut visuals = egui::Visuals::dark();
        visuals.panel_fill = egui::Color32::from_rgb(18, 20, 26);
        visuals.window_fill = egui::Color32::from_rgb(22, 25, 34);
        visuals.widgets.noninteractive.bg_fill = egui::Color32::from_rgb(25, 29, 40);
        ctx.set_visuals(visuals);

        egui::CentralPanel::default().show(ctx, |ui| {
            // Header Bar
            ui.horizontal(|ui| {
                ui.heading("⚡ IMF & WEFT Unified Neural-Symbolic Studio");
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.label(&self.log_status);
                    if ui.button("🔄 Refresh").clicked() {
                        self.refresh_antigravity_state();
                    }
                });
            });

            ui.add_space(4.0);

            // Navigation Tabs
            ui.horizontal(|ui| {
                ui.selectable_value(&mut self.selected_main_tab, 1, "💬 Live Interactive Chat (Streaming)");
                ui.selectable_value(&mut self.selected_main_tab, 0, "📡 Antigravity Sessions (IMF vs WEFT)");
            });

            ui.separator();

            if self.selected_main_tab == 1 {
                // TAB 1: Live Interactive Chat with Real-Time Word Streaming
                ui.horizontal(|ui| {
                    ui.label("Selected Engine:");
                    let current_label = match &self.selected_model {
                        ModelBackend::Ollama(m) => format!("Ollama: {}", m),
                        ModelBackend::HuggingFace(hf) => format!("HF Local: {}", hf),
                    };

                    egui::ComboBox::from_label("")
                        .selected_text(current_label)
                        .show_ui(ui, |ui| {
                            ui.heading("⚡ Fast Local Models");
                            ui.selectable_value(
                                &mut self.selected_model,
                                ModelBackend::Ollama(String::from("qwen2.5:14b")),
                                "qwen2.5:14b (Recommended: Fast & High Quality)",
                            );
                            ui.selectable_value(
                                &mut self.selected_model,
                                ModelBackend::HuggingFace(String::from("Qwen/Qwen2.5-0.5B")),
                                "Qwen/Qwen2.5-0.5B (Instant: 80+ tokens/s)",
                            );

                            ui.separator();
                            ui.heading("🧠 Large Reasoning & Vision Models");
                            ui.selectable_value(
                                &mut self.selected_model,
                                ModelBackend::Ollama(String::from("qwen3.8-27b:latest")),
                                "qwen3.8-27b:latest (Heavy 27B Reasoning)",
                            );
                            ui.selectable_value(
                                &mut self.selected_model,
                                ModelBackend::Ollama(String::from("qwen2.5vl:7b")),
                                "qwen2.5vl:7b (Vision-Language)",
                            );
                            ui.selectable_value(
                                &mut self.selected_model,
                                ModelBackend::HuggingFace(String::from("deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B")),
                                "DeepSeek-R1-Distill-Qwen-1.5B (Chain-of-Thought)",
                            );
                        });

                    if self.is_generating {
                        ui.colored_label(egui::Color32::from_rgb(255, 190, 60), "⚡ Streaming tokens live...");
                    }
                });

                ui.separator();

                // Chat Messages Feed
                egui::ScrollArea::vertical()
                    .max_height(ui.available_height() - 70.0)
                    .stick_to_bottom(true)
                    .show(ui, |ui| {
                        for msg in &self.user_chat_history {
                            let (badge_color, border_color) = if msg.sender.starts_with("👤") {
                                (egui::Color32::from_rgb(80, 160, 240), egui::Color32::from_rgb(35, 60, 95))
                            } else {
                                (egui::Color32::from_rgb(90, 220, 130), egui::Color32::from_rgb(30, 75, 45))
                            };

                            egui::Frame::group(ui.style())
                                .fill(border_color)
                                .inner_margin(egui::Margin::same(8.0))
                                .rounding(egui::Rounding::same(6.0))
                                .show(ui, |ui| {
                                    ui.horizontal(|ui| {
                                        ui.colored_label(badge_color, &msg.sender);
                                        ui.weak(&msg.timestamp);
                                        if msg.is_streaming {
                                            ui.colored_label(egui::Color32::from_rgb(255, 180, 50), "typing...");
                                        }
                                    });
                                    ui.add_space(2.0);
                                    ui.label(&msg.text);
                                });
                            ui.add_space(6.0);
                        }
                    });

                ui.separator();

                // Input Box
                ui.horizontal(|ui| {
                    let text_edit = ui.add(
                        egui::TextEdit::singleline(&mut self.chat_input)
                            .hint_text("Ask anything across general coding, reasoning, systems...")
                            .desired_width(ui.available_width() - 95.0),
                    );

                    let enter_pressed = text_edit.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter));

                    if ui.button("➤ Send").clicked() || enter_pressed {
                        self.send_chat_message();
                    }
                });

            } else {
                // TAB 0: Antigravity Session Logs (Separated IMF vs WEFT)
                ui.horizontal(|ui| {
                    ui.label("Active Antigravity Workspace:");
                    let was_imf = self.selected_convo_tab == ConversationSource::IMF;
                    if ui.selectable_label(was_imf, "🔬 IMF Project Session").clicked() {
                        self.selected_convo_tab = ConversationSource::IMF;
                        self.refresh_antigravity_state();
                    }
                    let was_weft = self.selected_convo_tab == ConversationSource::WEFT;
                    if ui.selectable_label(was_weft, "🧵 WEFT Project Session").clicked() {
                        self.selected_convo_tab = ConversationSource::WEFT;
                        self.refresh_antigravity_state();
                    }
                });

                ui.separator();

                let col_height = ui.available_height() - 30.0;
                ui.columns(2, |cols| {
                    // Left Column: Live Transcript for Selected Session
                    cols[0].heading("💬 Live Session Feed");
                    egui::ScrollArea::vertical()
                        .max_height(col_height)
                        .stick_to_bottom(true)
                        .show(&mut cols[0], |ui| {
                            for msg in &self.chat_entries {
                                let (tag, color) = match msg.source.as_str() {
                                    "USER_EXPLICIT" => ("👤 USER", egui::Color32::from_rgb(100, 200, 255)),
                                    "MODEL" => ("🤖 MODEL", egui::Color32::from_rgb(150, 255, 150)),
                                    _ => ("⚙ SYSTEM", egui::Color32::from_rgb(220, 220, 100)),
                                };

                                egui::Frame::group(ui.style())
                                    .fill(egui::Color32::from_rgb(26, 30, 42))
                                    .inner_margin(egui::Margin::same(6.0))
                                    .rounding(egui::Rounding::same(4.0))
                                    .show(ui, |ui| {
                                        ui.colored_label(color, format!("[Step {}] {}", msg.step, tag));
                                        if !msg.content.is_empty() {
                                            let preview: String = msg.content.chars().take(280).collect();
                                            ui.label(format!("  {}", preview));
                                        }
                                        if !msg.tool_calls.is_empty() {
                                            ui.weak(format!("  🔧 Tools: {}", msg.tool_calls.join(", ")));
                                        }
                                    });
                                ui.add_space(4.0);
                            }
                        });

                    // Right Column: Active Background Tasks
                    cols[1].heading("⚙ Active Background Tasks");
                    egui::ScrollArea::vertical()
                        .max_height(col_height)
                        .show(&mut cols[1], |ui| {
                            for t in &self.running_tasks {
                                egui::Frame::group(ui.style())
                                    .fill(egui::Color32::from_rgb(28, 34, 48))
                                    .inner_margin(egui::Margin::same(6.0))
                                    .rounding(egui::Rounding::same(4.0))
                                    .show(ui, |ui| {
                                        ui.horizontal(|ui| {
                                            ui.strong(&t.task_id);
                                            ui.weak(format!("({} KB)", t.size_bytes / 1024));
                                        });
                                        ui.add_space(2.0);
                                        ui.colored_label(egui::Color32::from_rgb(180, 210, 240), &t.last_log_line);
                                    });
                                ui.add_space(4.0);
                            }
                        });
                });
            }
        });
    }
}

fn main() -> eframe::Result<()> {
    let native_options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1040.0, 680.0])
            .with_min_inner_size([750.0, 500.0])
            .with_title("IMF & WEFT Unified Studio"),
        ..Default::default()
    };
    eframe::run_native(
        "IMF Studio",
        native_options,
        Box::new(|_cc| Ok(Box::new(ImfApp::default()))),
    )
}
