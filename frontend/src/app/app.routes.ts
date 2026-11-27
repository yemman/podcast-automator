import { Routes } from '@angular/router';
import { HomeComponent } from './pages/home/home.component';
import { EpisodeDetailComponent } from './pages/episode-detail/episode-detail.component';

export const routes: Routes = [
  {
    path: '',
    component: HomeComponent
  },
  {
    path: 'episode/:id',
    component: EpisodeDetailComponent
  },
  {
    path: '**',
    redirectTo: ''
  }
];
