//
//  Bus2hikeApp.swift
//  Bus2hikeApp
//
//  Created by Antonia Stieger on 30.01.26.
//

import SwiftUI

@main
struct Bus2hikeApp: App {
   
   @State var locationManager = LocationManager.shared
   
    var body: some Scene {
        WindowGroup {
            ContentView()
              .environment(locationManager)
        }
    }
}
