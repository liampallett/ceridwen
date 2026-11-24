//
//  ContentView.swift
//  Ceridwen
//
//  Created by Liam Pallett on 2026-11-23.
//

import SwiftUI

struct ContentView: View {
    // Thread/Messages
    @State private var threads: [ChatThread] = []
    @State private var selectedThreadID: String?
    @State private var selectedThreadMessageHistory: [Message] = []
    @State private var replyDraft = ""
    
    // Model
    @State private var models: [String] = []
    @AppStorage("selectedModel") private var selectedModel: String = "gemma4:12b-mlx"
    
    // Network
    @State private var connectionState: ConnectionState = .checking
    
    var body: some View {
        Group {
            switch connectionState {
            case .checking:
                ProgressView("Connecting")
                
            case .unreachable:
                ContentUnavailableView {
                    Label("Connection to backend failed", systemImage: "wifi.exclamationmark")
                } description: {
                    Text("Backend is offline. Check LaunchAgent service")
                } actions: {
                    Button("Retry") { Task { await connect() } }
                }
                
            case .connected:
                NavigationSplitView {
                    List(threads, selection: $selectedThreadID) { thread in
                        Text(thread.title.isEmpty ? "New thread" : thread.title)
                    }
                    .toolbar {
                        Button {
                            Task { await newThread() }
                        } label: {
                            Label("New thread", systemImage: "square.and.pencil")
                        }
                        .keyboardShortcut("n", modifiers: .command)
                    }
                } detail: {
                    if selectedThreadID != nil {
                        VStack(spacing: 0) {
                            MessageListView(messages: selectedThreadMessageHistory)
                            HStack {
                                TextField("Reply", text: $replyDraft)
                                    .onSubmit { Task { await send() } }
                                Button("Send") { Task { await send() } }
                                    .disabled(replyDraft.isEmpty)
                            }
                            HStack {
                                Spacer()
                                Menu {
                                    Picker("Model", selection: $selectedModel) {
                                        ForEach(models, id: \.self) { model in
                                            Text(model).tag(model)
                                        }
                                    }
                                    .pickerStyle(.inline)
                                    .labelsHidden()          // otherwise "Pet" appears as a heading inside the menu
                                } label: {
                                    Text(selectedModel)
                                }
                                .menuStyle(.borderlessButton)
                                .fixedSize()
                            }
                        }
                    } else {
                        Text("Pick a thread")
                    }
                }
            }
        }
        .task {
            await connect()
        }
        .task(id: selectedThreadID) {
            guard let selectedThreadID else {
                selectedThreadMessageHistory = []
                return
            }
            
            do {
                let url = URL(string: "http://127.0.0.1:8000/threads/\(selectedThreadID)/messages")!
                let (data, _) = try await URLSession.shared.data(from: url)
                let decoder = JSONDecoder()
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                selectedThreadMessageHistory = try decoder.decode([Message].self, from: data)
                print(selectedThreadMessageHistory)
            } catch {
                print("Failed:", error)
            }
        }
    }
    
    func connect() async {
        connectionState = .checking
        do {
            let url = URL(string: "http://127.0.0.1:8000/health")!
            let (_, response) = try await URLSession.shared.data(from: url)
            let status = (response as? HTTPURLResponse)?.statusCode
            if status == 200 {
                try await loadThreads()
                
                let modelsUrl = URL(string: "http://127.0.0.1:8000/models")!
                let(data, _) = try await URLSession.shared.data(from: modelsUrl)
                models = try JSONDecoder().decode([String].self, from: data)
                
                connectionState = .connected
            } else {
                print("[ceridwen] health returned status:", status as Any)
                connectionState = .unreachable
            }
        } catch {
            print("[ceridwen] connect failed:", error)
            connectionState = .unreachable
        }
    }
    
    func send() async {
        let decoder = JSONDecoder()
        
        guard let selectedThreadID, !replyDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        
        selectedThreadMessageHistory.append(Message(role: "user", content: replyDraft, toolName: nil))
        selectedThreadMessageHistory.append(Message(role: "assistant", content: "", toolName: nil))
        
        do {
            var request = URLRequest(url: URL(string: "http://127.0.0.1:8000/chat")!)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            
            let encoder = JSONEncoder()
            encoder.keyEncodingStrategy = .convertToSnakeCase
            request.httpBody = try encoder.encode(ChatRequestBody(model: selectedModel, message: replyDraft, threadId: selectedThreadID))
            
            replyDraft = ""
            
            let (bytes, _) = try await URLSession.shared.bytes(for: request)
            for try await line in bytes.lines {
                let event = try decoder.decode(ChatEvent.self, from: Data(line.utf8))
                switch event{
                case .content(let text):
                    selectedThreadMessageHistory[selectedThreadMessageHistory.count - 1].content += text
                case .thinking(let thinkingText):
                    selectedThreadMessageHistory[selectedThreadMessageHistory.count - 1].thinking += thinkingText
                case .toolCall(let toolCall):
                    selectedThreadMessageHistory[selectedThreadMessageHistory.count - 1].toolCalls.append(toolCall)
                case .toolResult(let toolResult):
                    selectedThreadMessageHistory.append(Message(role: "tool", content: toolResult.result, toolName: toolResult.name))
                    selectedThreadMessageHistory.append(Message(role: "assistant", content: "", toolName: nil))
                case .title(let newTitle):
                    if let index = threads.firstIndex(where: { $0.id == selectedThreadID }) {
                        threads[index].title = newTitle
                    }
                default:
                    break
                }
            }
            print(selectedThreadMessageHistory.map { "\($0.role): \($0.content)" })
        } catch {
            print("[ceridwen] send failed:", error)
        }
    }
    
    func loadThreads() async throws {
        let url = URL(string: "http://127.0.0.1:8000/threads")!
        let (data, _) = try await URLSession.shared.data(from: url)
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        threads = try decoder.decode([ChatThread].self, from: data)
    }
    
    func newThread() async {
        do {
            var request = URLRequest(url: URL(string: "http://127.0.0.1:8000/threads")!)
            request.httpMethod = "POST"
            let (data, _) = try await URLSession.shared.data(for: request)
            let created = try JSONDecoder().decode(NewThreadResponse.self, from: data)
            try await loadThreads()
            selectedThreadID = created.id
        } catch {
            print("[ceridwen] new thread failed:", error)
        }
    }
}


#Preview {
    ContentView()
}
