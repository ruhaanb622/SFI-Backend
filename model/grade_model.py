import pandas as pd
from sklearn.linear_model import LinearRegression

class GradePredictionModel:
    def __init__(self):
        # Load dataset
        data = pd.read_csv("datasets/ap_predict_data.csv")

        # Drop any rows without a grade
        data = data.dropna(subset=['Grade'])

        # Strip whitespace from column names
        data.columns = data.columns.str.strip()

        # Map Grade to percentage
        grade_map = {'A': 90, 'B': 80, 'C': 70, 'D': 60, 'F': 50}
        data['GradePercent'] = data['Grade'].map(grade_map)

        # Input features
        self.features = ['Attendance','Work Habits','Behavior','Timeliness','Advocacy','Tech Growth',
                         'Tech Sense','Tech Talk','Communication and Collaboration','Leadership','Integrity']

        X = data[self.features]
        y = data['GradePercent']

        # Fit the model
        self.model = LinearRegression()
        self.model.fit(X, y)

    def predict(self, user_input):
        # Validate input length
        if len(user_input) != len(self.features):
            raise ValueError(f"Expected {len(self.features)} inputs, got {len(user_input)}")

        # Binarize inputs (1-3 → 0, 4-5 → 1)
        binarized = [0 if x <= 3 else 1 for x in user_input]

        percent = self.model.predict([binarized])[0]
        percent = max(0, min(100, percent))

        # Convert percent to letter grade
        if percent >= 90:
            letter = 'A'
        elif percent >= 80:
            letter = 'B'
        elif percent >= 70:
            letter = 'C'
        elif percent >= 60:
            letter = 'D'
        else:
            letter = 'F'

        return round(percent, 2), letter
