import pandas as pd
import numpy as np



class Dataset:

    def __init__(self, csv_file):
        self.df = pd.read_csv(csv_file)
        self.special_combos = pd.read_csv("other data/specials.csv")
        self.monsters = pd.read_csv("other data/msm_monster_elements.csv")
        self.parent1_species_col = self.get_col("Parent 1 Species")
        self.parent2_species_col = self.get_col("Parent 2 Species")
        self.parent1_level_col = self.get_col("Parent 1 Level")
        self.parent2_level_col = self.get_col("Parent 2 Level")
        self.result_col = self.get_col("Result")
        self.torch_col = self.get_col("Torches")
        self.skin_col = self.get_col("Titan")

    def get_col(self, needle):
        for col in self.df.columns:
            if needle in col:
                return self.df[col]

    def remove_rarity(self, monster_name):
        low = monster_name.lower()
        if low.startswith("rare ") or low.startswith("epic ") or low.startswith("adult "):
            return monster_name.split(" ", 1)[1]
        return monster_name

    def export_results_grouped_by_combo(self, output_file="grouped_results.csv"):
        # groups results by unique variables, parents (order independent), levels, torch count, island skin
        results = {}

        for index, row in self.df.iterrows():

            p1 = self.remove_rarity(row[self.parent1_species_col.name])
            p2 = self.remove_rarity(row[self.parent2_species_col.name])

            l1 = row[self.parent1_level_col.name]
            l2 = row[self.parent2_level_col.name]

            torches = row[self.torch_col.name]

            skin = row[self.skin_col.name]

            key = tuple(sorted([(p1, l1), (p2, l2)])) + (torches, skin)

            result = row[self.result_col.name]

            if key not in results:
                results[key] = {"outcomes": {}}
            if result not in results[key]["outcomes"]:
                results[key]["outcomes"][result] = 0

            results[key]["outcomes"][result] += 1

        output_rows = []
        for key, value in results.items():
            (p1, l1), (p2, l2), torches, skin = key
            total_breeds = sum(value["outcomes"].values())
            outcome_list = [(result, count) for result, count in value["outcomes"].items()]
            output_rows.append((p1, l1, p2, l2, torches, skin, total_breeds, outcome_list))

        output_df = pd.DataFrame(
            output_rows, columns=["Parent 1 Species", "Parent 1 Level", "Parent 2 Species", "Parent 2 Level", "Torches", "Skin", "Total Breeds", "Outcomes"]
        )

        output_df.to_csv(output_file, index=False)
        print(f"Exported grouped results to {output_file}")



