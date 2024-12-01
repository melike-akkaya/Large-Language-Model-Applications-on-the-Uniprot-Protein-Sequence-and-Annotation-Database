# This script generates different bar graphs for each query type and model

import matplotlib.pyplot as plt

models = ["gemini-pro", "gemini-1.5-flash", "meta-llama-3.1-405b-instruct", "mistrall-small", "codestral-latest"]
query_types = ["simple queries", "complex queries", "curator-written queries"]

results = {
    "gemini-pro": {
        "simple": [9, 0, 42],
        "complex": [14, 0, 36],
        "curator-written": [6, 0, 13]
    },
    "gemini-1.5-flash": {
        "simple": [11, 0, 40],
        "complex": [14, 0, 36],
        "curator-written": [7, 0, 12]
    },
    "meta-llama-3.1-405b-instruct": {
        "simple": [9, 0, 42],
        "complex": [7, 0, 43],
        "curator-written": [6, 0, 13]
    },
    "mistrall-small": {
        "simple": [16, 0, 35],
        "complex": [19, 0, 31],
        "curator-written": [10, 0, 9]
    },
    "codestral-latest": {
        "simple": [5, 0, 46],
        "complex": [4, 0, 46],
        "curator-written": [4, 0, 15]
    }
}

total_queries = {
    "simple": 51,
    "complex": 50,
    "curator-written": 19
}

fig, axs = plt.subplots(nrows=3, ncols=5, figsize=(15, 10), sharex='col', sharey='row',
                        gridspec_kw={'hspace': 0.5, 'wspace': 0.3})

categories = ['NULL', 'ERROR', 'Correct Result']
colors = ['orange', 'red', 'blue']

for i, query_type in enumerate(query_types):
    query_key = query_type.split()[0].lower()
    for j, model in enumerate(models):
        data = results[model][query_key]
        normalized_data = [value / total_queries[query_key] * 100 for value in data]  # normalize to percentage

        axs[i, j].bar(categories, normalized_data, color=colors, edgecolor='black')
        axs[i, j].grid(True, which='both', linestyle='--', linewidth=0.5, color='grey', axis='both')

        axs[i, j].set_ylim(0, 100)

        if i == 0:
            axs[i, j].set_title(model, fontsize=9, fontweight='bold', pad=10)

        if j == 0:
            axs[i, j].set_ylabel(query_type, fontsize=9, fontweight='bold', labelpad=10)

plt.subplots_adjust(left=0.07, right=0.97, top=0.92, bottom=0.08)

fig.suptitle('Model Performance Analysis', fontsize=14, fontweight='bold')

plt.show()
