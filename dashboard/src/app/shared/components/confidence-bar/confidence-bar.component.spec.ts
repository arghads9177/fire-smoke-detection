import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ConfidenceBarComponent } from './confidence-bar.component';

describe('ConfidenceBarComponent', () => {
  let component: ConfidenceBarComponent;
  let fixture: ComponentFixture<ConfidenceBarComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ConfidenceBarComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ConfidenceBarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
