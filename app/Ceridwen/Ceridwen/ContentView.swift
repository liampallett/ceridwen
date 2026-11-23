//
//  ContentView.swift
//  Ceridwen
//
//  Created by Liam Pallett on 2026-11-23.
//

import SwiftUI

struct ContentView: View {
    @State private var threads: [ChatThread] = []
    @State private var selectedThreadID: String?
    @State private var messages: [Message] = []
    @State private var connectionState: ConnectionState = .checking
    @State private var draft = ""
    
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
                } detail: {
                    if selectedThreadID != nil {
                        VStack(spacing: 0) {
                            MessageListView(messages: messages)
                            HStack {
                                TextField("Reply", text: $draft)
                                    .onSubmit { Task { await send() } }
                                Button("Send") { Task { await send() } }
                                    .disabled(draft.isEmpty)
                            }
                            .padding()
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
                messages = []
                return
            }
            
            do {
                let url = URL(string: "http://127.0.0.1:8000/threads/\(selectedThreadID)/messages")!
                let (data, _) = try await URLSession.shared.data(from: url)
                let decoder = JSONDecoder()
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                messages = try decoder.decode([Message].self, from: data)
                print(messages)
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
                let threadsURL = URL(string: "http://127.0.0.1:8000/threads")!
                let (data, _) = try await URLSession.shared.data(from: threadsURL)
                let decoder = JSONDecoder()
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                threads = try decoder.decode([ChatThread].self, from: data)
                connectionState = .connected
            } else {
                connectionState = .unreachable
            }
        } catch {
            connectionState = .unreachable
        }
    }
    
    func send() async {
        guard let selectedThreadID else {
            return
        }
        
        do {
            var request = URLRequest(url: URL(string: "http://127.0.0.1:8000/chat")!)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            
            let encoder = JSONEncoder()
            encoder.keyEncodingStrategy = .convertToSnakeCase
            request.httpBody = try encoder.encode(ChatRequestBody(model: "gemma4:12b-mlx", message: draft, threadId: selectedThreadID))
            
            draft = ""
            
            let (bytes, _) = try await URLSession.shared.bytes(for: request)
            for try await line in bytes.lines {
                print(line)
            }
        } catch {
            print("[ceridwen] send failed:", error)
        }
    }
}


#Preview {
    ContentView()
}
