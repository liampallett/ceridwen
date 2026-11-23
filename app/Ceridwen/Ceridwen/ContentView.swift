//
//  ContentView.swift
//  Ceridwen
//
//  Created by Liam Pallett on 2026-11-23.
//

import SwiftUI

struct ContentView: View {
    @State private var threads: [ChatThread] = []

    var body: some View {
        NavigationSplitView {
            List(threads) { thread in
                Text(thread.title.isEmpty ? "New thread" : thread.title)
            }
        } detail: {
            Text("Pick a thread")
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
    }
}

#Preview {
    ContentView()
}
