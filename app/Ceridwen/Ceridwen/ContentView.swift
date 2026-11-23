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

    var body: some View {
        NavigationSplitView {
            List(threads, selection: $selectedThreadID) { thread in
                Text(thread.title.isEmpty ? "New thread" : thread.title)
            }
        } detail: {
            if selectedThreadID != nil {
            	MessageListView(messages: messages)
            } else {
                Text("Pick a thread")
            }
        }
        .task {
            do {
                let url = URL(string: "http://127.0.0.1:8000/threads")!
                let (data, _) = try await URLSession.shared.data(from: url)
                let decoder = JSONDecoder()
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                threads = try decoder.decode([ChatThread].self, from: data)
            } catch {
                print("Failed:", error)
            }
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
}

#Preview {
    ContentView()
}
