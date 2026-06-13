import { AsyncPipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { NavComponent } from './layout/nav/nav.component';
import { SocketService } from './core/services/socket.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, NavComponent, AsyncPipe],
  templateUrl: './app.component.html',
})
export class AppComponent implements OnInit {
  readonly connected$;

  constructor(private readonly socketService: SocketService) {
    this.connected$ = this.socketService.onConnectionChange();
  }

  ngOnInit(): void {
    this.socketService.connect();
  }
}
