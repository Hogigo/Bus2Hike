//
//  ContentView.swift
//  bus2hike
//
//  Created by Antonia Stieger on 03.02.26.
//

import SwiftUI

struct ContentView: View {
   @StateObject var mapVM = MapViewModel()
   
   @State private var selectedHike: Hike?
   @State private var selectedStop: Stop?
   
   @State private var filters = HikeFilters()
   @State var showSidebar = true
   @State var showAllHikes = false
   @State var showHikeDetailList = false
   @State var showDetailCard = false
   @State var showSearchArea = true
   
   var body: some View {
      ZStack(alignment: .leading) {
         
         MapView(vm: mapVM,
                 selectedStop: $selectedStop,
                 selectedHike: $selectedHike,
                 showAllHikes: $showAllHikes,
                 showSearchArea: $showSearchArea,
                 showDetailCard: $showDetailCard
         )
         .frame(maxWidth: .infinity, maxHeight: .infinity)
         
         if showHikeDetailList {
            HikeDetailList(
               hikes: $mapVM.hikes,
               selectedHike: $selectedHike,
               showList: $showHikeDetailList,
               isLoading: $mapVM.isLoading,
               onSelect: { hike in
                  // Zoom in on selected hike and color dark red
                  selectedHike = hike
                  if let mid = hike.midCoordinate {
                     withAnimation(.easeInOut) {
                        mapVM.zoomIn(on: mid)
                     }
                  }
                  showHikeDetailList = false
               },
               onClose: {
                  showHikeDetailList = false
               }
            )
         }
         
         if showSidebar {
            FilterSidebar(vm: mapVM,
                          filters: $filters,
                          showSidebar: $showSidebar,
                          selectedStop: $selectedStop,
                          showAllHikes: $showAllHikes,
                          showHikeDetailList: $showHikeDetailList,
                          onClose: {
               if let stop = selectedStop {
                  mapVM.zoomOut(from: stop.location)
               }
               selectedStop = nil
               showAllHikes = false
            }, onShowAllHikes: {
               withAnimation {
                  showHikeDetailList = true
               }
            })
            .transition(.move(edge: .leading))
         } else {
            CollapsedSidebar(showSidebar: $showSidebar)
         }
      }
      .onChange(of: selectedStop) {
         selectedHike = nil
         mapVM.hikes = []
         showAllHikes = false
         showHikeDetailList = false
      }
      .onChange(of: showHikeDetailList) {
         if showHikeDetailList {
            showDetailCard = false
            showSearchArea = false
         } else {
            showSearchArea = true
            showDetailCard = true
         }
      }
   }
}

