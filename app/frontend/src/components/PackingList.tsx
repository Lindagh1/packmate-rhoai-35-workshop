import type { PackingItem } from "../models/packmate";

interface PackingListProps {
  items: PackingItem[];
}

function groupByCategory(items: PackingItem[]): Array<[string, PackingItem[]]> {
  const groups = new Map<string, PackingItem[]>();
  for (const item of items) {
    const category = item.category.trim() || "Essentials";
    const existing = groups.get(category);
    if (existing) {
      existing.push(item);
    } else {
      groups.set(category, [item]);
    }
  }
  return Array.from(groups.entries());
}

export function PackingList({ items }: PackingListProps) {
  if (items.length === 0) {
    return <p className="lab-empty">No packing items were returned.</p>;
  }

  const grouped = groupByCategory(items);

  return (
    <div className="lab-packing-groups">
      {grouped.map(([category, categoryItems]) => (
        <section
          key={category}
          className="lab-packing-group"
          aria-labelledby={`packing-cat-${category}`}
        >
          <h4 className="lab-packing-group__title" id={`packing-cat-${category}`}>
            {category}
          </h4>
          <div className="lab-table-wrap">
            <table className="lab-table" aria-label={`Packing list: ${category}`}>
              <thead>
                <tr>
                  <th scope="col">Item</th>
                  <th scope="col">Qty</th>
                  <th scope="col">Reason</th>
                  <th scope="col">Priority</th>
                </tr>
              </thead>
              <tbody>
                {categoryItems.map((item) => (
                  <tr key={`${item.name}-${item.quantity}-${item.reason}`}>
                    <td data-label="Item">{item.name}</td>
                    <td data-label="Quantity">{item.quantity}</td>
                    <td data-label="Reason">{item.reason}</td>
                    <td data-label="Priority">
                      <span
                        className={`lab-badge ${
                          item.essential
                            ? "lab-badge--essential"
                            : "lab-badge--optional"
                        }`}
                      >
                        {item.essential ? "Essential" : "Optional"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
